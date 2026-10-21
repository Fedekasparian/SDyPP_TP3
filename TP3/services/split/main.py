"""Split: toma {job_id} de split.requests, parte cada archivo del job en
FRAGMENTS_PER_IMAGE franjas (con el solapamiento que pide la cadena de ops),
guarda los fragmentos en Redis y publica una tarea por fragmento."""
import json
import time

from tp3common import config, imaging, ops, rabbit, store
from tp3common.logging_setup import setup_logging
from tp3common.metrics import TASK_DURATION, TASK_ERRORS, TASKS_PROCESSED, start_health_server

SERVICE = "split"
log = setup_logging(SERVICE)


def handle(r, ch, method, body: bytes) -> None:
    job_id = json.loads(body)["job_id"]
    started = time.time()
    try:
        job = {k.decode(): v.decode() for k, v in r.hgetall(store.job_key(job_id)).items()}
        chain = json.loads(job["ops"])
        params = json.loads(job.get("params") or "{}")
        overlap = ops.required_overlap(chain)
        store.mark_time(r, job_id, "t_split_start")

        tasks = []
        for f in range(int(job["n_files"])):
            img = imaging.decode(r.get(store.input_key(job_id, f)))
            for s in imaging.split_strips(img, config.FRAGMENTS_PER_IMAGE, overlap):
                r.set(store.frag_key(job_id, f, s.index, "in"), imaging.encode_png(s.data),
                      ex=store.JOB_TTL_S)
                tasks.append({
                    "job_id": job_id, "file_idx": f, "frag_idx": s.index,
                    "fragment_id": f"{f}-{s.index}", "ops": chain, "params": params,
                    "worker_image": job["worker_image"], "pad_top": s.pad_top,
                    "core_h": s.core_h, "attempt": 0,
                })
        r.hset(store.job_key(job_id), mapping={
            "total_fragments": len(tasks),
            "frags_per_file": json.dumps(_count_per_file(tasks)),
        })
        store.mark_time(r, job_id, "t_split_end")
        for t in tasks:
            t["enqueued_at"] = time.time()
            rabbit.publish_json(ch, rabbit.EX_TASKS, job["worker_image"], t)
        ch.basic_ack(method.delivery_tag)
        TASKS_PROCESSED.labels(SERVICE).inc()
        TASK_DURATION.labels(SERVICE).observe(time.time() - started)
        log.info("job=%s partido en %d fragmentos", job_id, len(tasks))
    except Exception as exc:  # noqa: BLE001
        TASK_ERRORS.labels(SERVICE, type(exc).__name__).inc()
        log.exception("job=%s fallo el split", job_id)
        store.set_status(r, job_id, "failed", error=f"split: {exc}")
        ch.basic_ack(method.delivery_tag)


def _count_per_file(tasks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in tasks:
        counts[str(t["file_idx"])] = counts.get(str(t["file_idx"]), 0) + 1
    return counts


def main() -> None:
    r = store.connect()
    start_health_server(SERVICE, config.HEALTH_PORT, lambda: {"redis": "ok" if r.ping() else "down"})
    while True:
        conn = rabbit.connect()
        try:
            ch = conn.channel()
            rabbit.declare_topology(ch)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(rabbit.Q_SPLIT, lambda c, m, p, b: handle(r, c, m, b))
            log.info("split escuchando %s", rabbit.Q_SPLIT)
            ch.start_consuming()
        except Exception as exc:  # noqa: BLE001
            log.error("conexion perdida: %s", exc)
        finally:
            if conn.is_open:
                conn.close()


if __name__ == "__main__":
    main()
