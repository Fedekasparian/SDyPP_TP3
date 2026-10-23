import asyncio
import time
from unittest.mock import Mock

from backend import main
from dlq_monitor.main import on_result
from tp3common import store


def collect(initial, user=None):
    class Request:
        async def is_disconnected(self):
            return False

    async def run():
        return [event async for event in main._job_events(
            Request(), "j", user or {"sub": "alice", "exp": time.time() + 60}, initial,
        )]
    return asyncio.run(run())


def test_terminal_job_sends_snapshot_and_closes():
    events = collect({"status": "done", "progress_pct": 100})
    assert len(events) == 1 and "event: progress" in events[0]
    assert '"progress_pct": 100' in events[0]


def test_expired_stream_token_stops_before_reading_data():
    events = collect({"status": "processing"}, {"exp": time.time() - 1})
    assert len(events) == 1 and '"error": "unauthorized"' in events[0]


def test_stream_rereads_joiner_status_after_monitor_event(monkeypatch):
    r = Mock()
    r.xread.return_value = [(b"stream", [(b"1-0", {b"data": b'{"fragment_id":"0-0"}'})])]
    monkeypatch.setattr(main, "r", r)
    monkeypatch.setattr(main, "get_job", lambda *args: {"status": "done"})
    events = collect({"status": "processing"})
    assert any("event: result" in e for e in events)
    assert '"status": "done"' in events[-1]


def test_monitor_does_not_ack_if_redis_write_fails(monkeypatch):
    import pytest
    import redis

    monkeypatch.setattr(store, "record_result", Mock(side_effect=redis.ConnectionError()))
    channel = Mock()
    with pytest.raises(redis.ConnectionError):
        on_result(Mock(), channel, Mock(delivery_tag=1), b'{"job_id":"j"}')
    channel.basic_ack.assert_not_called()
