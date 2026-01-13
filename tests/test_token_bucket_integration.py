import os

from flask import Flask

import core.rate_limiter as rl
from core import metrics as metrics_mod
from core.app_factory import create_app


def _client_with_limits(defaults_json: str):
    os.environ["RATE_LIMIT_BACKEND"] = "memory"  # use memory backends
    rl._test_reset()
    app: Flask = create_app(
        {
            "TESTING": True,
            "FEATURE_LIMITS_DEFAULTS_JSON": defaults_json,
        }
    )
    return app.test_client()


def test_token_bucket_blocks_after_burst_and_strategy_tag(monkeypatch):
    events: list[tuple[str, dict]] = []

    class TM:  # minimal metrics harness
        def increment(self, name: str, tags):  # type: ignore[no-untyped-def]
            events.append((name, dict(tags or {})))

    monkeypatch.setattr(metrics_mod, "_metrics", TM())
    # Define limit test_endpoint with quota=3 per 60s using token bucket
    defaults = '{"test_endpoint": {"quota":3, "per_seconds":60, "strategy":"token_bucket"}}'
    c = _client_with_limits(defaults)
    # Consume exactly quota tokens (burst=quota) -> all allowed
    for _ in range(3):
        r = c.get("/_limit/test")
        assert r.status_code == 200, r.get_json()
    # Next should block
    r = c.get("/_limit/test")
    assert r.status_code == 429
    # Metrics should include at least one hit per outcome with strategy token_bucket
    allow_tags = [t for n, t in events if n == "rate_limit.hit" and t.get("outcome") == "allow"]
    block_tags = [t for n, t in events if n == "rate_limit.hit" and t.get("outcome") == "block"]
    assert any(t.get("strategy") == "token_bucket" for t in allow_tags)
    assert any(t.get("strategy") == "token_bucket" for t in block_tags)
