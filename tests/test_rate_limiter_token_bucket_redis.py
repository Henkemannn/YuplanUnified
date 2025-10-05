import os

import pytest
from flask import Flask

import core.rate_limiter as rl
from core import metrics as metrics_mod
from core.app_factory import create_app

pytestmark = [pytest.mark.redis]
redis = pytest.importorskip("redis", reason="redis-py not installed")


def _client_with_limits(defaults_json: str, redis_url: str):
    os.environ["RATE_LIMIT_BACKEND"] = "redis"
    os.environ["REDIS_URL"] = redis_url
    rl._test_reset()
    app: Flask = create_app({
        "TESTING": True,
        "FEATURE_LIMITS_DEFAULTS_JSON": defaults_json,
    })
    return app.test_client()


def _redis_url():
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")

@pytest.fixture(scope="module")
def redis_client():
    url = _redis_url()
    client = redis.Redis.from_url(url, socket_connect_timeout=0.2, socket_timeout=0.2)
    try:
        client.ping()
    except Exception:
        pytest.skip("Redis not available")
    client.flushdb()
    yield client
    client.flushdb()


def test_redis_token_bucket_allow_block(redis_client, monkeypatch):
    events: list[tuple[str, dict]] = []
    class TM:  # metrics capture
        def increment(self, name: str, tags):  # type: ignore[no-untyped-def]
            events.append((name, dict(tags or {})))
    monkeypatch.setattr(metrics_mod, "_metrics", TM())
    defaults = '{"test_endpoint": {"quota":5, "per_seconds":60, "strategy":"token_bucket"}}'
    c = _client_with_limits(defaults, _redis_url())
    for _ in range(5):
        r = c.get("/_limit/test")
        assert r.status_code == 200, r.get_json()
    r = c.get("/_limit/test")
    assert r.status_code == 429
    # ensure strategy tag present in a block hit
    block_tags = [t for n,t in events if n=="rate_limit.hit" and t.get("outcome")=="block"]
    assert any(t.get("strategy")=="token_bucket" for t in block_tags)


def test_redis_token_bucket_refill(redis_client):
    # Basic behavioural: ensure after window passes we can allow again (fallback uses fixed allow since retry_after simple)
    defaults = '{"test_endpoint": {"quota":2, "per_seconds":3, "strategy":"token_bucket"}}'
    c = _client_with_limits(defaults, _redis_url())
    assert c.get("/_limit/test").status_code == 200
    assert c.get("/_limit/test").status_code == 200
    assert c.get("/_limit/test").status_code == 429
    import time as _t
    _t.sleep(3.2)  # wait out full window so capacity refilled
    assert c.get("/_limit/test").status_code == 200
