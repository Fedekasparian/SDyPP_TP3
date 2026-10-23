"""Redis y RabbitMQ reales. Activar con TP3_INTEGRATION=1 en un entorno aislado.

Las colas llevan un prefijo aleatorio; Redis exige una base vacia y se borran
solamente las claves creadas por cada prueba. No se utiliza FLUSHDB.
"""
import json
import os
import threading
import time
import uuid
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tp3common import auth, config, imaging, ops, rabbit, store

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv("TP3_INTEGRATION") != "1", reason="Requiere Redis y RabbitMQ aislados",
)]
PNG = imaging.encode_png(np.arange(256, dtype=np.uint8).reshape(16, 16))


@pytest.fixture
def stack(monkeypatch):
    from backend import main

    monkeypatch.setattr(config, "AUTH_SECRET", uuid.uuid4().hex)
    monkeypatch.setattr(config, "REDIS_URL", os.environ["REDIS_URL"])
    monkeypatch.setattr(config, "RABBIT_URL", os.environ["RABBIT_URL"])
    r = store.connect()
    assert r.dbsize() == 0, "Usar una base Redis vacia y exclusiva para estas pruebas"
    monkeypatch.setattr(main, "r", r)
    monkeypatch.setattr(main, "_local", threading.local())

    prefix = "integration." + uuid.uuid4().hex + "."
    for name in ("EX_TASKS", "EX_TASKS_DLX", "EX_RESULTS", "Q_SPLIT", "Q_DLQ", "Q_PARKED",
                 "Q_RESULTS_JOINER", "Q_RESULTS_MONITOR"):
        monkeypatch.setattr(rabbit, name, prefix + getattr(rabbit, name))
    monkeypatch.setattr(rabbit, "task_queue", lambda pool: prefix + "tasks." + pool)
    connections = []
    connect = rabbit.connect

    def tracked_connect(*args, **kwargs):
        conn = connect(*args, **kwargs)
        connections.append(conn)
        return conn

    monkeypatch.setattr(rabbit, "connect", tracked_connect)
    conn = rabbit.connect(max_attempts=1)
    ch = conn.channel()
    rabbit.declare_topology(ch)
    users = {name: {"Authorization": "Bearer " + auth.issue_token(name, role)}
             for name, role in (("alice", "user"), ("bob", "user"), ("admin", "admin"))}
    try:
        with TestClient(main.app) as client:
            yield SimpleNamespace(client=client, r=r, ch=ch, users=users, api=main)
    finally:
        if conn.is_open:
            for queue in (rabbit.Q_SPLIT, rabbit.Q_DLQ, rabbit.Q_PARKED,
                          rabbit.Q_RESULTS_JOINER, rabbit.Q_RESULTS_MONITOR,
                          *(rabbit.task_queue(p) for p in config.ALLOWED_WORKER_IMAGES)):
                ch.queue_delete(queue)
            for exchange in (rabbit.EX_TASKS, rabbit.EX_TASKS_DLX, rabbit.EX_RESULTS):
                ch.exchange_delete(exchange)
        for connection in connections:
            if connection.is_open:
                connection.close()
        keys = list(r.scan_iter())
        if keys:
            r.delete(*keys)
        r.close()


def submit(stack, **data):
    return stack.client.post("/jobs", headers=stack.users["alice"],
                             files={"files": ("image.png", PNG, "image/png")},
                             data={"ops": "blur,sobel", **data})


def take(stack, queue, handler):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        method, _, body = stack.ch.basic_get(queue, auto_ack=False)
        if method:
            handler(stack.r, stack.ch, method, body)
            return body
        time.sleep(.02)
    pytest.fail(f"No llego mensaje a {queue}")


def finish(stack, job_id):
    from split.main import handle as split
    from worker.main import handle as worker
    from joiner.main import handle as join
    from dlq_monitor.main import on_result

    take(stack, rabbit.Q_SPLIT, split)
    total = int(stack.r.hget(store.job_key(job_id), "total_fragments"))
    for _ in range(total):
        take(stack, rabbit.task_queue(config.WORKER_POOL), worker)
        take(stack, rabbit.Q_RESULTS_JOINER, join)
        take(stack, rabbit.Q_RESULTS_MONITOR, on_result)


def test_submit_status_result_and_progress_with_real_services(stack):
    response = submit(stack)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert stack.client.get(f"/jobs/{job_id}", headers=stack.users["alice"]).json()["status"] == "queued"
    finish(stack, job_id)
    status = stack.client.get(f"/jobs/{job_id}", headers=stack.users["alice"]).json()
    assert status["status"] == "done" and status["progress_pct"] == 100
    assert status["workers"] and all(value is not None for value in status["timings_s"].values())
    result = stack.client.get(status["results"][0], headers=stack.users["alice"])
    np.testing.assert_array_equal(imaging.decode(result.content), ops.apply_chain(imaging.decode(PNG), ["blur", "sobel"]))
    assert stack.r.xlen(store.event_key(job_id)) == status["fragments"]["total"]
    stream = stack.client.get(f"/jobs/{job_id}/events", headers=stack.users["alice"])
    assert stream.status_code == 200 and stream.headers["content-type"].startswith("text/event-stream")
    assert '"status": "done"' in stream.text
    for suffix in ("workers", "done", "meta", "events", "events:seen"):
        assert 0 < stack.r.ttl(f"job:{job_id}:{suffix}") <= store.JOB_TTL_S


def test_roles_ownership_and_stream_are_enforced(stack):
    job_id = submit(stack).json()["job_id"]
    assert stack.client.get("/jobs").status_code == 401
    assert stack.client.get("/stats", headers=stack.users["alice"]).status_code == 403
    for path in (f"/jobs/{job_id}", f"/jobs/{job_id}/events", f"/jobs/{job_id}/result/0"):
        assert stack.client.get(path, headers=stack.users["bob"]).status_code == 404
    assert stack.client.get("/jobs/missing", headers=stack.users["alice"]).status_code == 404
    assert stack.client.get("/jobs", headers=stack.users["bob"]).json() == {"jobs": []}
    assert stack.client.get(f"/jobs/{job_id}", headers=stack.users["admin"]).status_code == 200
    assert stack.client.get("/stats", headers=stack.users["admin"]).status_code == 200


@pytest.mark.parametrize("fields,expected", [
    ({"ops": "rotate"}, "unsupported_op"),
    ({"worker_image": "unknown"}, "worker_image_not_allowed"),
    ({"params": "no-json"}, "invalid_params"),
    ({"ops": ""}, "missing_ops"),
])
def test_invalid_inputs_never_enter_queue(stack, fields, expected):
    response = submit(stack, **fields)
    assert response.status_code == 400
    assert response.json()["error"] == expected
    assert rabbit.queue_depth(stack.ch, rabbit.Q_SPLIT) == 0
    assert stack.r.scard("jobs:all") == 0


def test_corrupt_and_oversize_files_never_enter_queue(stack, monkeypatch):
    response = stack.client.post("/jobs", headers=stack.users["alice"],
        files={"files": ("bad.png", b"invalid")}, data={"ops": "sobel"})
    assert response.status_code == 400 and response.json()["error"] == "invalid_image"
    monkeypatch.setattr(config, "MAX_FILE_MB", .00001)
    assert submit(stack).status_code == 413
    assert rabbit.queue_depth(stack.ch, rabbit.Q_SPLIT) == 0


def test_missing_fields_have_documented_error_shape(stack):
    response = stack.client.post("/jobs", headers=stack.users["alice"], data={"ops": "sobel"})
    assert response.status_code == 400
    assert set(response.json()) == {"error", "detail"}
    assert rabbit.queue_depth(stack.ch, rabbit.Q_SPLIT) == 0


def test_rate_limit_is_shared_in_redis(stack, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 1)
    assert stack.client.get("/jobs", headers=stack.users["alice"]).status_code == 200
    response = stack.client.get("/jobs", headers=stack.users["alice"])
    assert response.status_code == 429 and response.json()["error"] == "rate_limited"


def test_expired_job_disappears_from_lists_and_stats(stack):
    job_id = submit(stack).json()["job_id"]
    stack.r.pexpire(store.job_key(job_id), 1)
    time.sleep(.02)
    assert stack.client.get("/jobs", headers=stack.users["alice"]).json() == {"jobs": []}
    assert stack.client.get("/stats", headers=stack.users["admin"]).json()["jobs_by_status"]["queued"] == 0


def test_monitor_deduplicates_and_does_not_recreate_expired_jobs(stack):
    job_id = submit(stack).json()["job_id"]
    result = {"job_id": job_id, "fragment_id": "0-0", "attempt": 0}
    assert store.record_result(stack.r, result)
    assert not store.record_result(stack.r, result)
    assert stack.r.xlen(store.event_key(job_id)) == 1
    stack.r.delete(store.job_key(job_id), store.event_key(job_id), f"job:{job_id}:events:seen")
    assert not store.record_result(stack.r, result)
    assert not stack.r.exists(store.event_key(job_id))
    store.set_status(stack.r, job_id, "dlq", error="late message")
    assert not stack.r.exists(store.job_key(job_id))


def test_admin_reprocess_confirms_and_requeues_parked_task(stack):
    job_id = submit(stack).json()["job_id"]
    store.set_status(stack.r, job_id, "dlq")
    task = {"job_id": job_id, "worker_image": config.WORKER_POOL, "attempt": 4}
    rabbit.publish_json(stack.ch, "", rabbit.Q_PARKED, task)
    response = stack.client.post("/admin/dlq/reprocess?max_messages=1", headers=stack.users["admin"])
    assert response.status_code == 200 and response.json()["reprocessed"] == 1
    method, _, body = stack.ch.basic_get(rabbit.task_queue(config.WORKER_POOL), auto_ack=True)
    assert method and json.loads(body)["attempt"] == 0
    assert rabbit.queue_depth(stack.ch, rabbit.Q_PARKED) == 0
    assert stack.r.hget(store.job_key(job_id), "status") == b"processing"


def test_health_checks_both_real_dependencies(stack):
    response = stack.client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"backend": "ok", "redis": "ok", "rabbitmq": "ok"}
