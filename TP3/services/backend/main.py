"""Backend HTTP (FastAPI). Stateless (R4): identidad en cada request (Bearer
token HMAC), estado en Redis, trabajo en RabbitMQ. Ver docs/contrato.md (R3)."""
import json
import threading
import time
import uuid

from fastapi import Depends, FastAPI, File, Form, Header, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from tp3common import auth, config, rabbit, store
from tp3common.logging_setup import recent_logs, setup_logging
from tp3common.metrics import HTTP_DURATION

from .validation import ValidationError, parse_ops, parse_params, parse_worker_image, validate_files

SERVICE = "backend"
log = setup_logging(SERVICE)
app = FastAPI(title="TP3 Sobel API", version="1.0.0")
app.mount("/metrics", make_asgi_app())
r = store.connect()


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=exc.status)


@app.exception_handler(ValidationError)
async def _validation_error(_: Request, exc: ValidationError):
    return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=exc.status)


@app.exception_handler(Exception)
async def _unexpected_error(_: Request, exc: Exception):
    log.exception("error inesperado")
    return JSONResponse({"error": "internal_error", "detail": "Error interno"}, status_code=500)


@app.middleware("http")
async def _metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    HTTP_DURATION.labels(request.method, path, response.status_code).observe(time.perf_counter() - start)
    return response


# ---------- RabbitMQ: una conexion por thread (pika no es thread-safe) ----------
_local = threading.local()


def publish(exchange: str, routing_key: str, body: dict) -> None:
    for attempt in (1, 2):
        try:
            ch = getattr(_local, "ch", None)
            if ch is None or ch.is_closed:
                _local.conn = rabbit.connect(max_attempts=2)
                _local.ch = _local.conn.channel()
                rabbit.declare_topology(_local.ch)
            rabbit.publish_json(_local.ch, exchange, routing_key, body)
            return
        except Exception as exc:  # noqa: BLE001
            _local.ch = None
            if attempt == 2:
                raise ApiError(503, "broker_unavailable", f"RabbitMQ no disponible: {exc}") from exc


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
    try:
        r.ping()
        status["redis"] = "ok"
    except Exception:  # noqa: BLE001
        status["redis"] = "down"
    return JSONResponse(status, status_code=200 if all(v == "ok" for v in status.values()) else 503)


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
    payload = [(f.filename or f"file{i}", await f.read()) for i, f in enumerate(files)]
    validate_files(payload)

    job_id = uuid.uuid4().hex
    pipe = r.pipeline()
    for i, (_, data) in enumerate(payload):
        pipe.set(store.input_key(job_id, i), data, ex=store.JOB_TTL_S)
    pipe.hset(store.job_key(job_id), mapping={
        "owner": user["sub"], "ops": json.dumps(chain), "params": json.dumps(op_params),
        "worker_image": image, "n_files": len(payload), "retries": 0, "t_submit": time.time(),
    })
    pipe.expire(store.job_key(job_id), store.JOB_TTL_S)
    pipe.sadd("jobs:all", job_id)
    pipe.sadd(f"jobs:user:{user['sub']}", job_id)
    pipe.execute()
    store.set_status(r, job_id, "queued")
    publish("", rabbit.Q_SPLIT, {"job_id": job_id})
    log.info("job=%s user=%s ops=%s files=%d encolado", job_id, user["sub"], chain, len(payload))
    return {"job_id": job_id, "status": "queued", "status_url": f"/jobs/{job_id}"}


@app.get("/jobs")
def list_jobs(user: dict = Depends(current_user)):
    key = "jobs:all" if user["role"] == "admin" else f"jobs:user:{user['sub']}"
    return {"jobs": sorted(j.decode() for j in r.smembers(key))}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(current_user)):
    return _job_view(job_id, _load_job(job_id, user))


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
    by_status = {s: r.scard(f"jobs:status:{s}") for s in store.STATUSES}
    lat = sorted(float(x) for x in r.lrange("stats:latencies", 0, -1))

    def pct(p: float):
        return round(lat[min(len(lat) - 1, int(p * len(lat)))], 4) if lat else None

    queues = {}
    try:
        conn = rabbit.connect(max_attempts=1)
        ch = conn.channel()
        for q in [rabbit.Q_SPLIT, rabbit.Q_DLQ, rabbit.Q_PARKED] + [
            rabbit.task_queue(p) for p in config.ALLOWED_WORKER_IMAGES
        ]:
            queues[q] = rabbit.queue_depth(ch, q)
        conn.close()
    except Exception as exc:  # noqa: BLE001
        queues = {"error": str(exc)}
    finished = by_status["done"] + by_status["failed"] + by_status["dlq"]
    return {
        "jobs_by_status": by_status,
        "queues": queues,
        "active_workers": store.active_workers(r),
        "latency_s": {"p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99), "samples": len(lat)},
        "error_rate": round((by_status["failed"] + by_status["dlq"]) / finished, 4) if finished else 0.0,
    }


@app.post("/admin/dlq/reprocess")
def reprocess_dlq(max_messages: int = 1000, _: dict = Depends(require_admin)):
    """Mueve los fragmentos estacionados (tasks.parked) de vuelta a la cola de trabajo."""
    conn = rabbit.connect(max_attempts=2)
    ch = conn.channel()
    moved, jobs = 0, set()
    while moved < max_messages:
        method, _, body = ch.basic_get(rabbit.Q_PARKED)
        if method is None:
            break
        task = json.loads(body)
        task.update(attempt=0, enqueued_at=time.time())
        rabbit.publish_json(ch, rabbit.EX_TASKS, task["worker_image"], task)
        ch.basic_ack(method.delivery_tag)
        jobs.add(task["job_id"])
        moved += 1
    for job_id in jobs:
        store.set_status(r, job_id, "processing", error="")
    conn.close()
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
