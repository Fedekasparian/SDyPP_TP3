import pytest

from tp3common import auth
from tp3common.retry import backoff_delays, retry_with_backoff

SECRET = "test-secret"


def test_token_roundtrip():
    claims = auth.verify_token(auth.issue_token("alice", "user", secret=SECRET), secret=SECRET)
    assert claims["sub"] == "alice" and claims["role"] == "user"


def test_tampered_token_rejected():
    token = auth.issue_token("alice", "user", secret=SECRET)
    with pytest.raises(auth.AuthError):
        auth.verify_token(token, secret="otro-secret")
    with pytest.raises(auth.AuthError):
        auth.verify_token(token[:-2] + "xx", secret=SECRET)


def test_expired_token_rejected():
    token = auth.issue_token("alice", "admin", ttl_s=-1, secret=SECRET)
    with pytest.raises(auth.AuthError):
        auth.verify_token(token, secret=SECRET)


def test_backoff_sequence_capped_at_30():
    gen = backoff_delays(30)
    assert [next(gen) for _ in range(7)] == [1, 2, 4, 8, 16, 30, 30]


def test_retry_gives_up(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def boom():
        calls.append(1)
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        retry_with_backoff(boom, "test", max_attempts=3)
    assert len(calls) == 3
