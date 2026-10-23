"""Joiner: consume results.joiner (fanout `results`). Cuando estan todos los
fragmentos de un job, recompone cada archivo y marca el job como done."""
import json
import time

from tp3common import config, imaging, rabbit, store
from tp3common.logging_setup import setup_logging
from tp3common.metrics import TASK_DURATION, TASK_ERRORS, TASKS_PROCESSED, start_health_server

SERVICE = "joiner"
log = setup_logging(SERVICE)


def assemble(r, job_id: str, job: dict) -> None:
    per_file = json.loads(job["frags_per_file"])
    meta = {
        k.decode(): json.loads(v)
        for k, v in r.hgetall(f"job:{job_id}:meta").items()
    }
    for f, count in per_file.items():
        cores = []
        for n in range(count):
            m = meta[f"{f}-{n}"]
            frag = imaging.decode(r.get(store.frag_key(job_id, int(f), n, "out")))
            cores.append(imaging.crop_core(frag, m["pad_top"], m["core_h"]))
        r.set(store.output_key(job_id, int(f)), imaging.encode_png(imaging.join_strips(cores)),
              ex=store.JOB_TTL_S)


def handle(r, ch, method, body: bytes) -> None:
    res = json.loads(body)
    job_id = res["job_id"]
    started = time.time()
    try:
        jk = store.job_key(job_id)
        r.hset(f"job:{job_id}:meta", res["fragment_id"],
               json.dumps({"pad_top": res["pad_top"], "core_h": res["core_h"]}))
        r.sadd(f"job:{job_id}:done", res["fragment_id"])
        store.expire_job_keys(r, job_id, f"job:{job_id}:done", f"job:{job_id}:meta")
        store.mark_time(r, job_id, "t_proc_end")
        job = {k.decode(): v.decode() for k, v in r.hgetall(jk).items()}
        total = int(job.get("total_fragments", 0))
        # SET NX: si hay varias replicas del joiner, solo una arma el resultado.
        if total and r.scard(f"job:{job_id}:done") >= total and r.set(f"job:{job_id}:joining", 1, nx=True, ex=600):
            assemble(r, job_id, job)
            store.mark_time(r, job_id, "t_join_end")
            store.set_status(r, job_id, "done")
            latency = time.time() - float(job["t_submit"])
            r.lpush("stats:latencies", latency)
            r.ltrim("stats:latencies", 0, 4999)
            r.expire("stats:latencies", store.JOB_TTL_S)
            log.info("job=%s DONE (%d fragmentos, %.2fs end-to-end)", job_id, total, latency)
        ch.basic_ack(method.delivery_tag)
        TASKS_PROCESSED.labels(SERVICE).inc()
        TASK_DURATION.labels(SERVICE).observe(time.time() - started)
    except Exception as exc:  # noqa: BLE001
        TASK_ERRORS.labels(SERVICE, type(exc).__name__).inc()
        log.exception("job=%s fallo el join", job_id)
        store.set_status(r, job_id, "failed", error=f"join: {exc}")
        ch.basic_ack(method.delivery_tag)


def main() -> None:
    r = store.connect()
    start_health_server(SERVICE, config.HEALTH_PORT, lambda: {"redis": "ok" if r.ping() else "down"})
    while True:
        conn = rabbit.connect()
        try:
            ch = conn.channel()
            rabbit.declare_topology(ch)
            ch.basic_qos(prefetch_count=10)
            ch.basic_consume(rabbit.Q_RESULTS_JOINER, lambda c, m, p, b: handle(r, c, m, b))
            log.info("joiner escuchando %s", rabbit.Q_RESULTS_JOINER)
            ch.start_consuming()
        except Exception as exc:  # noqa: BLE001
            log.error("conexion perdida: %s", exc)
        finally:
            if conn.is_open:
                conn.close()


if __name__ == "__main__":
    main()
