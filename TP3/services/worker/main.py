"""Worker: consume fragmentos de tasks.<WORKER_POOL>, aplica la cadena de operaciones
y publica el resultado en el fanout `results`.

- prefetch=1 + ack manual: si el worker muere, RabbitMQ reentrega el fragmento a otro.
- Excepcion al procesar -> nack sin requeue -> DLX -> tasks.dlq (lo toma el dlq-monitor).
- FAIL_RATE (0..1) simula fallos para probar la DLQ y las pruebas de carga (R5).
"""
import json
import os
import random
import socket
import threading
import time
import uuid

from tp3common import config, imaging, ops, rabbit, store
from tp3common.logging_setup import setup_logging
from tp3common.metrics import TASK_DURATION, TASK_ERRORS, TASKS_PROCESSED, start_health_server

SERVICE = "worker"
WORKER_ID = os.getenv("WORKER_ID") or f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
FAIL_RATE = float(os.getenv("FAIL_RATE", "0"))
log = setup_logging(SERVICE)


def heartbeat_loop(r) -> None:
    while True:
        try:
            store.worker_heartbeat(r, WORKER_ID)
        except Exception as exc:  # noqa: BLE001
            log.warning("heartbeat fallo: %s", exc)
        time.sleep(5)


def handle(r, ch, method, body: bytes) -> None:
    task = json.loads(body)
    job_id, f, n = task["job_id"], task["file_idx"], task["frag_idx"]
    started = time.time()
    try:
        if FAIL_RATE and random.random() < FAIL_RATE:
            raise RuntimeError("fallo simulado (FAIL_RATE)")
        r.sadd(f"job:{job_id}:workers", WORKER_ID)
        store.expire_job_keys(r, job_id, f"job:{job_id}:workers")
        store.mark_time(r, job_id, "t_proc_start", only_first=True)
        if r.hget(store.job_key(job_id), "status") == b"queued":
            store.set_status(r, job_id, "processing")

        data = r.get(store.frag_key(job_id, f, n, "in"))
        if data is None:
            raise RuntimeError("fragmento no encontrado en Redis")
        out = ops.apply_chain(imaging.decode(data), task["ops"], task.get("params"))
        r.set(store.frag_key(job_id, f, n, "out"), imaging.encode_png(out), ex=store.JOB_TTL_S)

        result = {
            k: task[k]
            for k in ("job_id", "file_idx", "frag_idx", "fragment_id", "pad_top", "core_h", "attempt")
        }
        result.update(worker_id=WORKER_ID, started_at=started, finished_at=time.time())
        rabbit.publish_json(ch, rabbit.EX_RESULTS, "", result)
        ch.basic_ack(method.delivery_tag)
        TASKS_PROCESSED.labels(SERVICE).inc()
        TASK_DURATION.labels(SERVICE).observe(time.time() - started)
        # redelivered=True: otro worker lo tenia sin ack y murio (Hit #1, etapa 3).
        log.info("job=%s frag=%s ok en %.3fs (intento %s%s)", job_id, task["fragment_id"],
                 time.time() - started, task.get("attempt", 0),
                 ", reentregado" if method.redelivered else "")
    except Exception as exc:  # noqa: BLE001
        TASK_ERRORS.labels(SERVICE, type(exc).__name__).inc()
        log.error("job=%s frag=%s fallo: %s -> DLQ", job_id, task.get("fragment_id"), exc)
        ch.basic_nack(method.delivery_tag, requeue=False)


def main() -> None:
    r = store.connect()
    start_health_server(SERVICE, config.HEALTH_PORT, lambda: {"redis": "ok" if r.ping() else "down"})
    threading.Thread(target=heartbeat_loop, args=(r,), daemon=True).start()
    queue = rabbit.task_queue(config.WORKER_POOL)
    while True:  # reconexion con backoff si RabbitMQ se cae
        conn = rabbit.connect()
        try:
            ch = conn.channel()
            rabbit.declare_topology(ch)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue, lambda c, m, p, b: handle(r, c, m, b))
            log.info("worker %s escuchando %s", WORKER_ID, queue)
            ch.start_consuming()
        except Exception as exc:  # noqa: BLE001
            log.error("conexion perdida: %s", exc)
        finally:
            if conn.is_open:
                conn.close()


if __name__ == "__main__":
    main()
