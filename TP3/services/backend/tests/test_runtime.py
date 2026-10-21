import asyncio
import threading
from unittest.mock import Mock

import pika
import pytest
import redis
from fastapi.testclient import TestClient

from backend import main
from tp3common import store


def test_submission_moves_blocking_work_off_event_loop(monkeypatch):
    from starlette.datastructures import UploadFile
    from io import BytesIO

    loop_thread = threading.get_ident()
    seen = []

    def enqueue(*args):
        seen.append(threading.get_ident())
        return {"job_id": "test"}

    monkeypatch.setattr(main, "_enqueue_job", enqueue)
    result = asyncio.run(main.submit_job(
        files=[UploadFile(BytesIO(b"image"), filename="a.png")], ops="sobel",
        worker_image=None, params=None, user={"sub": "alice"},
    ))
    assert result == {"job_id": "test"}
    assert seen and seen[0] != loop_thread


def test_publish_retries_and_reports_sanitized_503(monkeypatch):
    sleeps = []
    connect = Mock(side_effect=pika.exceptions.AMQPConnectionError("private connection details"))
    monkeypatch.setattr(main.rabbit, "connect", connect)
    monkeypatch.setattr("tp3common.retry.time.sleep", sleeps.append)
    monkeypatch.setattr(main._local, "ch", None, raising=False)
    monkeypatch.setattr(main._local, "conn", None, raising=False)
    with pytest.raises(main.ApiError) as exc:
        main.publish("", "split.requests", {"job_id": "x"})
    assert exc.value.status == 503
    assert "private" not in exc.value.detail
    assert connect.call_count == 5
    assert sleeps == [1, 2, 4, 8]


def test_redis_reads_retry_but_increments_do_not(monkeypatch):
    sleeps = []
    execute = Mock(side_effect=[redis.ConnectionError(), redis.TimeoutError(), b"value"])
    monkeypatch.setattr(redis.Redis, "execute_command", execute)
    monkeypatch.setattr("tp3common.retry.time.sleep", sleeps.append)
    client = store.RuntimeRedis()
    assert client.get("key") == b"value"
    assert sleeps == [1, 2]
    execute.reset_mock(side_effect=True)
    execute.side_effect = redis.ConnectionError()
    with pytest.raises(redis.ConnectionError):
        client.incr("counter")
    assert execute.call_count == 1


def test_redis_programming_error_not_retried(monkeypatch):
    operation = Mock(side_effect=redis.ResponseError("WRONGTYPE"))
    with pytest.raises(redis.ResponseError):
        store.retry_operation(operation)
    assert operation.call_count == 1


def test_health_detects_broker_down(monkeypatch):
    probe = Mock()
    probe.__enter__ = Mock(return_value=probe)
    probe.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(redis.Redis, "from_url", Mock(return_value=probe))
    monkeypatch.setattr(main.rabbit, "connect", Mock(side_effect=pika.exceptions.AMQPConnectionError()))
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"backend": "ok", "redis": "ok", "rabbitmq": "down"}
    assert response.headers["X-Backend-Replica"]


def test_reprocess_does_not_ack_on_publish_failure(monkeypatch):
    conn, channel = Mock(), Mock()
    conn.channel.return_value = channel
    channel.basic_get.return_value = (Mock(delivery_tag=3), None, b'{"job_id":"j","worker_image":"tp3-worker"}')
    monkeypatch.setattr(main.rabbit, "connect", Mock(return_value=conn))
    monkeypatch.setattr(main.rabbit, "declare_topology", Mock())
    monkeypatch.setattr(main.store, "set_status", Mock())
    monkeypatch.setattr(main, "publish", Mock(side_effect=main.ApiError(503, "broker_unavailable", "down")))
    with pytest.raises(main.ApiError):
        main.reprocess_dlq(max_messages=1, _={"role": "admin"})
    channel.basic_ack.assert_not_called()
    conn.close.assert_called_once()


def test_queue_monitor_recovers_when_initial_connection_fails(monkeypatch):
    from dlq_monitor import main as monitor

    class StopLoop(BaseException):
        pass

    sleeps = []
    connection = Mock()
    monkeypatch.setattr(monitor.rabbit, "connect", Mock(side_effect=[
        pika.exceptions.AMQPConnectionError(), connection,
    ]))
    monkeypatch.setattr(monitor.rabbit, "declare_topology", Mock())
    monkeypatch.setattr(monitor.rabbit, "queue_depth", Mock(return_value=0))

    def sleep(seconds):
        sleeps.append(seconds)
        if seconds == 5:
            raise StopLoop()

    monkeypatch.setattr(monitor.time, "sleep", sleep)
    with pytest.raises(StopLoop):
        monitor.queue_depth_loop()
    assert sleeps == [1, 5]
    connection.close.assert_called_once()
