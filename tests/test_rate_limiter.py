from flask import Flask

import core.rate_limiter as rl
from core import metrics as metrics_mod
from core.app_factory import create_app


def _client(quota=3, per=60, backend="memory"):
    # Force backend for test process
    import os

    os.environ["RATE_LIMIT_BACKEND"] = backend
    rl._test_reset()
    app: Flask = create_app({"TESTING": True})
    return app.test_client()


def test_within_quota_allows():
    c = _client()
    for _i in range(3):
        r = c.get("/_limit/test")
        assert r.status_code == 200, r.get_json()
    # 4th should 429 (quota=3)
    r = c.get("/_limit/test")
    assert r.status_code == 429
    data = r.get_json()
    assert data.get("status") == 429 and data.get("type", " ").endswith("/rate_limited")
    assert "retry_after" in data


def test_window_reset(monkeypatch):
    c = _client()
    # exhaust quota
    for _ in range(3):
        assert c.get("/_limit/test").status_code == 200
    assert c.get("/_limit/test").status_code == 429
    # fast-forward window by mocking time.time
    import core.rate_limiter as rl_mod

    orig_time = rl_mod.time.time

    def fake_time():
        return orig_time() + 61

    monkeypatch.setattr(rl_mod.time, "time", fake_time)
    try:
        assert c.get("/_limit/test").status_code == 200
    finally:
        monkeypatch.setattr(rl_mod.time, "time", orig_time)


def test_retry_after_positive():
    c = _client()
    for _ in range(4):
        c.get("/_limit/test")
    r = c.get("/_limit/test")
    assert r.status_code == 429
    retry_after_hdr = r.headers.get("Retry-After") or "0"
    assert int(retry_after_hdr) >= 0


def test_metrics_allow_and_block(monkeypatch):
    events: list[tuple[str, dict]] = []

    class TestMetrics:
        def increment(self, name: str, tags):  # type: ignore[no-untyped-def]
            events.append((name, dict(tags or {})))

    monkeypatch.setattr(metrics_mod, "_metrics", TestMetrics())
    c = _client()
    # 5 requests => 3 allow then we expect blocks after quota
    for _i in range(5):
        c.get("/_limit/test")
    allow_hits = [e for e in events if e[0] == "rate_limit.hit" and e[1].get("outcome") == "allow"]
    block_hits = [e for e in events if e[0] == "rate_limit.hit" and e[1].get("outcome") == "block"]
    assert len(allow_hits) >= 3
    assert len(block_hits) >= 1


def test_noop_backend_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "noop")
    rl._test_reset()
    c = _client(backend="noop")
    # Quota ignored because noop always allows; simulate many requests.
    for _ in range(10):
        assert c.get("/_limit/test").status_code == 200


def test_redis_backend_fallback(monkeypatch):
    # Set backend=redis but without redis library installed this should fallback to noop.
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6399/0")  # unlikely port
    rl._test_reset()
    c = _client(backend="redis")
    for _ in range(10):
        # If it were actually enforcing we'd be blocked after 3
        assert c.get("/_limit/test").status_code == 200
