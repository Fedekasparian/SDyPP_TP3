"""Estado compartido en Redis (contrato del Paso 0). Los servicios son stateless (R4):
todo lo que hay que recordar entre requests vive aca.

Claves:
    job:{id}                      hash  owner, status, ops, params, worker_image, n_files,
                                        total_fragments, retries, t_submit, t_split_start,
                                        t_split_end, t_proc_start, t_proc_end, t_join_end, error
    job:{id}:done                 set   fragment_ids terminados (idempotente ante duplicados)
    job:{id}:workers              set   worker_ids que participaron
    job:{id}:in:{file}            bytes archivo original
    job:{id}:frag:{file}:{n}:in   bytes fragmento de entrada (PNG)
    job:{id}:frag:{file}:{n}:out  bytes fragmento procesado (PNG)
    job:{id}:out:{file}           bytes resultado final (PNG)
    jobs:all                      set   todos los job_ids
    jobs:user:{user}              set   job_ids de un usuario
    jobs:status:{status}          set   job_ids por estado (para /stats)
    stats:latencies               list  duraciones end-to-end en segundos (ultimas 5000)
    worker:alive:{worker_id}      str   heartbeat con TTL
    ratelimit:{user}:{minuto}     int   contador de requests
"""
import time

import redis

from . import config
from .retry import retry_with_backoff

STATUSES = ("queued", "processing", "done", "failed", "dlq")
JOB_TTL_S = 24 * 3600


def connect(url: str | None = None) -> redis.Redis:
    r = redis.Redis.from_url(url or config.REDIS_URL)
    retry_with_backoff(r.ping, "redis")
    return r


def job_key(job_id: str) -> str:
    return f"job:{job_id}"


def input_key(job_id: str, file_idx: int) -> str:
    return f"job:{job_id}:in:{file_idx}"


def frag_key(job_id: str, file_idx: int, frag_idx: int, kind: str) -> str:
    return f"job:{job_id}:frag:{file_idx}:{frag_idx}:{kind}"


def output_key(job_id: str, file_idx: int) -> str:
    return f"job:{job_id}:out:{file_idx}"


def set_status(r: redis.Redis, job_id: str, status: str, **fields) -> None:
    assert status in STATUSES, status
    pipe = r.pipeline()
    for s in STATUSES:
        pipe.srem(f"jobs:status:{s}", job_id)
    pipe.sadd(f"jobs:status:{status}", job_id)
    pipe.hset(job_key(job_id), mapping={"status": status, **{k: str(v) for k, v in fields.items()}})
    pipe.execute()


def mark_time(r: redis.Redis, job_id: str, field: str, only_first: bool = False) -> None:
    if only_first:
        r.hsetnx(job_key(job_id), field, time.time())
    else:
        r.hset(job_key(job_id), field, time.time())


def worker_heartbeat(r: redis.Redis, worker_id: str, ttl_s: int = 15) -> None:
    r.set(f"worker:alive:{worker_id}", time.time(), ex=ttl_s)


def active_workers(r: redis.Redis) -> list[str]:
    return [k.decode().split(":", 2)[2] for k in r.scan_iter("worker:alive:*")]
