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
import json
import time

import redis

from . import config
from .retry import retry_with_backoff

STATUSES = ("queued", "processing", "done", "failed", "dlq")
JOB_TTL_S = 24 * 3600
TRANSIENT_ERRORS = (redis.ConnectionError, redis.TimeoutError)


def retry_operation(fn):
    """Reintenta operaciones idempotentes; nunca usar para INCR/LPUSH sin deduplicar."""
    return retry_with_backoff(fn, "redis", max_attempts=5, exceptions=TRANSIENT_ERRORS)


class RuntimeRedis(redis.Redis):
    """Las lecturas pueden repetirse tras una desconexion sin duplicar escrituras."""
    READ_COMMANDS = {"GET", "HGET", "HGETALL", "SMEMBERS", "SCARD", "LRANGE", "EXISTS",
                     "TTL", "PTTL", "PING", "XREAD", "XREVRANGE"}

    def execute_command(self, *args, **options):
        execute = super().execute_command
        if args and args[0] in self.READ_COMMANDS:
            return retry_operation(lambda: execute(*args, **options))
        return execute(*args, **options)


def connect(url: str | None = None) -> redis.Redis:
    r = RuntimeRedis.from_url(url or config.REDIS_URL, socket_connect_timeout=3,
                             socket_timeout=5, health_check_interval=15)
    return r


def expire_job_keys(r, job_id: str, *keys: str) -> None:
    """Las claves auxiliares nunca sobreviven al hash principal del job."""
    ttl = r.pttl(job_key(job_id))
    expires_at = int(time.time() * 1000) + ttl
    def expire():
        pipe = r.pipeline()
        for key in keys:
            if ttl > 0:
                pipe.pexpireat(key, expires_at)
            else:
                pipe.delete(key)
        pipe.execute()
    retry_operation(expire)


def active_job_ids(r, index: str) -> list[str]:
    """Conserva el contrato de sets y limpia IDs cuyos jobs ya expiraron."""
    ids = sorted(r.smembers(index))
    if not ids:
        return []
    def check():
        pipe = r.pipeline()
        for jid in ids:
            pipe.exists(job_key(jid.decode()))
        return pipe.execute()
    alive = retry_operation(check)
    stale = [jid for jid, exists in zip(ids, alive) if not exists]
    if stale:
        retry_operation(lambda: r.srem(index, *stale))
    return [jid.decode() for jid, exists in zip(ids, alive) if exists]


def event_key(job_id: str) -> str:
    return f"job:{job_id}:events"


def record_result(r, result: dict) -> bool:
    """Fanout -> stream acotado, deduplicado y con el mismo TTL que el job."""
    job_id = result["job_id"]
    script = """
    local ttl = redis.call('PTTL', KEYS[1])
    if ttl <= 0 then return 0 end
    if redis.call('SADD', KEYS[3], ARGV[1]) == 0 then return 0 end
    redis.call('XADD', KEYS[2], 'MAXLEN', '=', 256, '*', 'data', ARGV[2])
    redis.call('PEXPIRE', KEYS[2], ttl)
    redis.call('PEXPIRE', KEYS[3], ttl)
    return 1
    """
    identity = f"{result['fragment_id']}:{result.get('attempt', 0)}"
    return bool(retry_operation(lambda: r.eval(
        script, 3, job_key(job_id), event_key(job_id), f"job:{job_id}:events:seen",
        identity, json.dumps(result),
    )))


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
    script = """
    if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
    for i = 3, #KEYS do redis.call('SREM', KEYS[i], ARGV[1]) end
    redis.call('SADD', KEYS[2], ARGV[1])
    redis.call('EXPIRE', KEYS[2], ARGV[2])
    redis.call('HSET', KEYS[1], unpack(ARGV, 3))
    return 1
    """
    keys = [job_key(job_id), f"jobs:status:{status}"] + [f"jobs:status:{s}" for s in STATUSES]
    values = ["status", status]
    for key, value in fields.items():
        values.extend((key, str(value)))
    retry_operation(lambda: r.eval(script, len(keys), *keys, job_id, JOB_TTL_S, *values))


def mark_time(r: redis.Redis, job_id: str, field: str, only_first: bool = False) -> None:
    if only_first:
        r.hsetnx(job_key(job_id), field, time.time())
    else:
        r.hset(job_key(job_id), field, time.time())


def worker_heartbeat(r: redis.Redis, worker_id: str, ttl_s: int = 15) -> None:
    r.set(f"worker:alive:{worker_id}", time.time(), ex=ttl_s)


def active_workers(r: redis.Redis) -> list[str]:
    return [k.decode().split(":", 2)[2] for k in r.scan_iter("worker:alive:*")]
