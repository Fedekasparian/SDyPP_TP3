"""Backend HTTP (FastAPI). Stateless (R4): identidad en cada request (Bearer
token HMAC), estado en Redis, trabajo en RabbitMQ. Ver docs/contrato.md (R3)."""
import json
import socket
import threading
import time
import uuid

import pika
import redis

from fastapi import Depends, FastAPI, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import make_asgi_app

from tp3common import auth, config, rabbit, store
from tp3common.retry import retry_with_backoff
from tp3common.logging_setup import recent_logs, setup_logging
from tp3common.metrics import HTTP_DURATION

from .validation import ValidationError, parse_ops, parse_params, parse_worker_image, validate_files

SERVICE = "backend"
log = setup_logging(SERVICE)
app = FastAPI(title="TP3 Sobel API", version="1.0.0")
app.mount("/metrics", make_asgi_app())
r = store.connect()
REPLICA_ID = socket.gethostname()
SSE_DURATION_S = 55


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=exc.status)


@app.exception_handler(ValidationError)
async def _validation_error(_: Request, exc: ValidationError):
    return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def _request_error(_: Request, exc: RequestValidationError):
    return JSONResponse({"error": "invalid_request", "detail": "Faltan campos o tienen un formato invalido"},
                        status_code=400)


@app.exception_handler(redis.RedisError)
async def _redis_error(_: Request, exc: redis.RedisError):
    log.error("Redis no disponible: %s", type(exc).__name__)
    return JSONResponse({"error": "store_unavailable", "detail": "Redis no disponible"}, status_code=503)


@app.exception_handler(Exception)
async def _unexpected_error(_: Request, exc: Exception):
    log.exception("error inesperado")
    return JSONResponse({"error": "internal_error", "detail": "Error interno"}, status_code=500)


@app.middleware("http")
async def _metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Backend-Replica"] = REPLICA_ID
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    HTTP_DURATION.labels(request.method, path, response.status_code).observe(time.perf_counter() - start)
    return response


# ---------- RabbitMQ: una conexion por thread (pika no es thread-safe) ----------
_local = threading.local()


def publish(exchange: str, routing_key: str, body: dict) -> None:
    def send():
        try:
            ch = getattr(_local, "ch", None)
            if ch is None or ch.is_closed:
                _local.conn = rabbit.connect(max_attempts=1)
                _local.ch = _local.conn.channel()
                rabbit.declare_topology(_local.ch)
                _local.ch.confirm_delivery()
            _local.ch.basic_publish(
                exchange=exchange, routing_key=routing_key, body=json.dumps(body).encode(),
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
                mandatory=True,
            )
        except pika.exceptions.AMQPError:
            _local.ch = None
            conn = getattr(_local, "conn", None)
            if conn is not None and conn.is_open:
                try:
                    conn.close()
                except pika.exceptions.AMQPError:
                    pass
            raise
    try:
        retry_with_backoff(send, "publish", max_attempts=5,
                           exceptions=(pika.exceptions.AMQPError, OSError))
    except (pika.exceptions.AMQPError, OSError) as exc:
        raise ApiError(503, "broker_unavailable", "RabbitMQ no disponible; no se confirmo el envio") from exc


# ---------- Auth (R4) ----------
def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "unauthorized", "Falta header Authorization: Bearer <token>")
    try:
        claims = auth.verify_token(authorization.split(" ", 1)[1])
    except auth.AuthError as exc:
        raise ApiError(401, "unauthorized", str(exc)) from exc
    _rate_limit(claims["sub"])
    return claims


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise ApiError(403, "forbidden", "Requiere rol admin")
    return user


def _rate_limit(sub: str) -> None:
    key = f"ratelimit:{sub}:{int(time.time() // 60)}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 120)
    if count > config.RATE_LIMIT_PER_MIN:
        raise ApiError(429, "rate_limited", f"Maximo {config.RATE_LIMIT_PER_MIN} requests/minuto")


def _load_job(job_id: str, user: dict) -> dict:
    raw = r.hgetall(store.job_key(job_id))
    # 404 tanto si no existe como si es de otro usuario: no revelamos que existe.
    if not raw:
        raise ApiError(404, "not_found", "Job inexistente")
    job = {k.decode(): v.decode() for k, v in raw.items()}
    if user["role"] != "admin" and job["owner"] != user["sub"]:
        raise ApiError(404, "not_found", "Job inexistente")
    return job


def _job_view(job_id: str, job: dict) -> dict:
    total = int(job.get("total_fragments", 0) or 0)
    done = r.scard(f"job:{job_id}:done")
    t = {k: float(v) for k, v in job.items() if k.startswith("t_")}

    def span(a: str, b: str):
        return round(t[b] - t[a], 4) if a in t and b in t else None

    return {
        "job_id": job_id,
        "status": job["status"],
        "owner": job["owner"],
        "ops": json.loads(job["ops"]),
        "worker_image": job["worker_image"],
        "files": int(job["n_files"]),
        "fragments": {"total": total, "done": done},
        "progress_pct": round(100 * done / total, 1) if total else 0.0,
        "timings_s": {
            "split": span("t_split_start", "t_split_end"),
            "queue": span("t_split_end", "t_proc_start"),
            "processing": span("t_proc_start", "t_proc_end"),
            "join": span("t_proc_end", "t_join_end"),
            "total": span("t_submit", "t_join_end"),
        },
        "workers": sorted(w.decode() for w in r.smembers(f"job:{job_id}:workers")),
        "retries": int(job.get("retries", 0)),
        "error": job.get("error"),
        "results": [f"/jobs/{job_id}/result/{i}" for i in range(int(job["n_files"]))]
        if job["status"] == "done" else [],
    }


# ---------- Endpoints ----------
@app.get("/health")
def health():
    status = {SERVICE: "ok"}
    # Probes rapidos: no aplicar los reintentos de las operaciones de negocio.
    try:
        with redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=2, socket_timeout=2) as probe:
            probe.ping()
        status["redis"] = "ok"
    except redis.RedisError:
        status["redis"] = "down"
    conn = None
    try:
        conn = rabbit.connect(max_attempts=1)
        status["rabbitmq"] = "ok"
    except (pika.exceptions.AMQPError, OSError):
        status["rabbitmq"] = "down"
    finally:
        if conn is not None and conn.is_open:
            conn.close()
    return JSONResponse(status, status_code=200 if all(v == "ok" for v in status.values()) else 503)


def _enqueue_job(payload, chain, image, op_params, user):
    validate_files(payload)
    job_id = uuid.uuid4().hex
    submitted = time.time()

    def save():
        # Reconstruir el pipeline en cada intento: execute() vacia su buffer.
        pipe = r.pipeline()
        for i, (_, data) in enumerate(payload):
            pipe.set(store.input_key(job_id, i), data, ex=store.JOB_TTL_S)
        pipe.hset(store.job_key(job_id), mapping={
            "owner": user["sub"], "ops": json.dumps(chain), "params": json.dumps(op_params),
            "worker_image": image, "n_files": len(payload), "retries": 0,
            "t_submit": submitted, "status": "queued",
        })
        pipe.expire(store.job_key(job_id), store.JOB_TTL_S)
        for index in ("jobs:all", f"jobs:user:{user['sub']}", "jobs:status:queued"):
            pipe.sadd(index, job_id)
            pipe.expire(index, store.JOB_TTL_S)
        pipe.execute()

    store.retry_operation(save)
    try:
        publish("", rabbit.Q_SPLIT, {"job_id": job_id})
    except ApiError:
        store.set_status(r, job_id, "failed", error="No se pudo confirmar el envio a RabbitMQ")
        raise
    log.info("job=%s user=%s ops=%s files=%d encolado", job_id, user["sub"], chain, len(payload))
    return {"job_id": job_id, "status": "queued", "status_url": f"/jobs/{job_id}"}


@app.post("/jobs", status_code=202)
async def submit_job(
    files: list[UploadFile] = File(...),
    ops: str = Form(..., description="Operaciones encadenadas separadas por coma, ej: blur,sobel"),
    worker_image: str | None = Form(default=None),
    params: str | None = Form(default=None, description='JSON, ej: {"threshold": {"threshold": 90}}'),
    user: dict = Depends(current_user),
):
    # R2: todo se valida ANTES de tocar RabbitMQ.
    chain = parse_ops(ops)
    image = parse_worker_image(worker_image)
    op_params = parse_params(params)
    if len(files) > config.MAX_FILES:
        raise ValidationError(400, "too_many_files", f"Maximo {config.MAX_FILES} archivos")
    payload = []
    for i, f in enumerate(files):
        data = await f.read(int(config.MAX_FILE_MB * 1024 * 1024) + 1)
        if len(data) > config.MAX_FILE_MB * 1024 * 1024:
            raise ValidationError(413, "file_too_large", f"'{f.filename}' supera {config.MAX_FILE_MB} MB")
        payload.append((f.filename or f"file{i}", data))
    # PIL, Redis y pika son bloqueantes; nunca ocupar el event loop de ASGI.
    return await run_in_threadpool(_enqueue_job, payload, chain, image, op_params, user)


@app.get("/jobs")
def list_jobs(user: dict = Depends(current_user)):
    key = "jobs:all" if user["role"] == "admin" else f"jobs:user:{user['sub']}"
    return {"jobs": store.active_job_ids(r, key)}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(current_user)):
    return _job_view(job_id, _load_job(job_id, user))


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _job_events(request: Request, job_id: str, user: dict, initial: dict):
    snapshot, previous = initial, None
    cursor = "0-0"
    deadline = time.monotonic() + SSE_DURATION_S
    try:
        while not await request.is_disconnected():
            if user["exp"] <= time.time():
                yield _sse("error", {"error": "unauthorized", "detail": "Token expirado"})
                return
            if snapshot != previous:
                yield _sse("progress", snapshot)
                previous = snapshot
            if snapshot["status"] in ("done", "failed", "dlq"):
                return
            if time.monotonic() >= deadline:
                yield _sse("reconnect", {"detail": "Reconectar para continuar"})
                return
            # XREAD bloquea como maximo un segundo, fuera del event loop.
            entries = await run_in_threadpool(
                lambda: r.xread({store.event_key(job_id): cursor}, count=50, block=1000)
            )
            if user["exp"] <= time.time():
                yield _sse("error", {"error": "unauthorized", "detail": "Token expirado"})
                return
            for _, messages in entries:
                for event_id, fields in messages:
                    cursor = event_id.decode()
                    yield _sse("result", json.loads(fields[b"data"]))
            # Joiner y monitor consumen copias independientes: volver a leer el
            # estado evita perder el 'done' si el monitor recibio el fanout antes.
            snapshot = await run_in_threadpool(get_job, job_id, user)
            yield ": keep-alive\n\n"
    except redis.RedisError:
        yield _sse("error", {"error": "store_unavailable", "detail": "Redis no disponible"})
    except ApiError as exc:
        yield _sse("error", {"error": exc.code, "detail": exc.detail})


@app.get("/jobs/{job_id}/events", response_class=StreamingResponse)
async def job_events(request: Request, job_id: str, user: dict = Depends(current_user)):
    # Autorizar antes de enviar headers SSE: un tercero obtiene 404, no un stream.
    initial = await run_in_threadpool(get_job, job_id, user)
    return StreamingResponse(_job_events(request, job_id, user, initial), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/jobs/{job_id}/result/{file_idx}")
def get_result(job_id: str, file_idx: int, user: dict = Depends(current_user)):
    job = _load_job(job_id, user)
    if job["status"] != "done":
        raise ApiError(404, "not_ready", f"Job en estado {job['status']}")
    data = r.get(store.output_key(job_id, file_idx))
    if data is None:
        raise ApiError(404, "not_found", "Resultado inexistente")
    return Response(data, media_type="image/png")


@app.get("/stats")
def stats(_: dict = Depends(require_admin)):
    by_status = {s: len(store.active_job_ids(r, f"jobs:status:{s}")) for s in store.STATUSES}
    lat = sorted(float(x) for x in r.lrange("stats:latencies", 0, -1))

    def pct(p: float):
        return round(lat[min(len(lat) - 1, int(p * len(lat)))], 4) if lat else None

    queues = {}
    conn = None
    try:
        conn = rabbit.connect(max_attempts=1)
        ch = conn.channel()
        for q in [rabbit.Q_SPLIT, rabbit.Q_DLQ, rabbit.Q_PARKED] + [
            rabbit.task_queue(p) for p in config.ALLOWED_WORKER_IMAGES
        ]:
            queues[q] = rabbit.queue_depth(ch, q)
    except (pika.exceptions.AMQPError, OSError):
        queues = {"error": "RabbitMQ no disponible"}
    finally:
        if conn is not None and conn.is_open:
            conn.close()
    finished = by_status["done"] + by_status["failed"] + by_status["dlq"]
    return {
        "jobs_by_status": by_status,
        "queues": queues,
        "active_workers": store.active_workers(r),
        "latency_s": {"p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99), "samples": len(lat)},
        "error_rate": round((by_status["failed"] + by_status["dlq"]) / finished, 4) if finished else 0.0,
    }


@app.post("/admin/dlq/reprocess")
def reprocess_dlq(max_messages: int = Query(default=1000, ge=1, le=1000),
                  _: dict = Depends(require_admin)):
    """Ack solo tras persistir el estado y confirmar la republicacion."""
    conn = None
    moved, jobs = 0, set()
    try:
        conn = rabbit.connect(max_attempts=5)
        ch = conn.channel()
        rabbit.declare_topology(ch)
        while moved < max_messages:
            method, _, body = ch.basic_get(rabbit.Q_PARKED, auto_ack=False)
            if method is None:
                break
            try:
                task = json.loads(body)
                job_id, pool = task["job_id"], task["worker_image"]
            except (ValueError, KeyError, TypeError) as exc:
                raise ApiError(500, "invalid_dlq_message", "Mensaje estacionado invalido; requiere revision") from exc
            task.update(attempt=0, enqueued_at=time.time())
            store.set_status(r, job_id, "processing", error="")
            try:
                publish(rabbit.EX_TASKS, pool, task)
            except ApiError:
                store.set_status(r, job_id, "dlq", error="No se pudo confirmar el reproceso")
                raise
            ch.basic_ack(method.delivery_tag)
            jobs.add(job_id)
            moved += 1
    except (pika.exceptions.AMQPError, OSError) as exc:
        raise ApiError(503, "broker_unavailable", "RabbitMQ no disponible durante el reproceso") from exc
    finally:
        if conn is not None and conn.is_open:
            try:
                conn.close()  # reentrega cualquier mensaje no confirmado
            except pika.exceptions.AMQPError:
                pass
    return {"reprocessed": moved, "jobs": sorted(jobs)}


@app.post("/admin/tokens")
def create_token(sub: str, role: str = "user", _: dict = Depends(require_admin)):
    """Emite tokens para usuarios/bots (usado por las pruebas de carga)."""
    try:
        return {"sub": sub, "role": role, "token": auth.issue_token(sub, role)}
    except auth.AuthError as exc:
        raise ApiError(400, "invalid_role", str(exc)) from exc


@app.get("/admin/logs")
def logs(n: int = 100, _: dict = Depends(require_admin)):
    return {"logs": recent_logs(n)}
