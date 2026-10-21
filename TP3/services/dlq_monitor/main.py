"""DLQ monitor:
- tasks.dlq: reasigna el fragmento (attempt+1) a otro worker hasta MAX_RETRIES;
  despues lo estaciona en tasks.parked y marca el job como `dlq` (el admin lo
  puede reprocesar con POST /admin/dlq/reprocess).
- results.monitor: copia del fanout de resultados para el dashboard de progreso.
- Publica la profundidad de las colas como metrica `tasks_queued`.
"""
import json
import threading
import time

from tp3common import config, rabbit, store
from tp3common.logging_setup import setup_logging
from tp3common.metrics import TASK_ERRORS, TASKS_PROCESSED, TASKS_QUEUED, start_health_server

SERVICE = "dlq-monitor"
log = setup_logging(SERVICE)


def on_dlq(r, ch, method, body: bytes) -> None:
    task = json.loads(body)
    job_id = task["job_id"]
    task["attempt"] = int(task.get("attempt", 0)) + 1
    r.hincrby(store.job_key(job_id), "retries", 1)
    if task["attempt"] <= config.MAX_RETRIES:
        task["enqueued_at"] = time.time()
        rabbit.publish_json(ch, rabbit.EX_TASKS, task["worker_image"], task)
        log.warning("job=%s frag=%s reasignado (intento %d/%d)", job_id, task["fragment_id"],
                    task["attempt"], config.MAX_RETRIES)
    else:
        rabbit.publish_json(ch, "", rabbit.Q_PARKED, task)
        store.set_status(r, job_id, "dlq", error=f"fragmento {task['fragment_id']} agoto reintentos")
        TASK_ERRORS.labels(SERVICE, "max_retries").inc()
        log.error("job=%s frag=%s agoto reintentos -> parked", job_id, task["fragment_id"])
    ch.basic_ack(method.delivery_tag)


def on_result(r, ch, method, body: bytes) -> None:
    TASKS_PROCESSED.labels(SERVICE).inc()
    ch.basic_ack(method.delivery_tag)


def queue_depth_loop() -> None:
    conn = rabbit.connect()
    ch = conn.channel()
    queues = [rabbit.Q_SPLIT, rabbit.Q_DLQ, rabbit.Q_PARKED] + [
        rabbit.task_queue(p) for p in config.ALLOWED_WORKER_IMAGES
    ]
    while True:
        for q in queues:
            try:
                TASKS_QUEUED.labels(q).set(rabbit.queue_depth(ch, q))
            except Exception as exc:  # noqa: BLE001
                log.warning("no pude leer %s: %s", q, exc)
                conn = rabbit.connect()
                ch = conn.channel()
        time.sleep(5)


def main() -> None:
    r = store.connect()
    start_health_server(SERVICE, config.HEALTH_PORT, lambda: {"redis": "ok" if r.ping() else "down"})
    threading.Thread(target=queue_depth_loop, daemon=True).start()
    while True:
        conn = rabbit.connect()
        try:
            ch = conn.channel()
            rabbit.declare_topology(ch)
            ch.basic_qos(prefetch_count=10)
            ch.basic_consume(rabbit.Q_DLQ, lambda c, m, p, b: on_dlq(r, c, m, b))
            ch.basic_consume(rabbit.Q_RESULTS_MONITOR, lambda c, m, p, b: on_result(r, c, m, b))
            log.info("dlq-monitor escuchando %s y %s", rabbit.Q_DLQ, rabbit.Q_RESULTS_MONITOR)
            ch.start_consuming()
        except Exception as exc:  # noqa: BLE001
            log.error("conexion perdida: %s", exc)
        finally:
            if conn.is_open:
                conn.close()


if __name__ == "__main__":
    main()
