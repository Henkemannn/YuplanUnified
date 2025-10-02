from __future__ import annotations

import json
from typing import Any

from flask import Flask

from core.app_factory import create_app
from core.limit_registry import refresh
from core.rate_limiter import _test_reset
import os


def _app(overrides: dict[str, Any] | str | None = None, defaults: dict[str, Any] | str | None = None) -> Flask:
    # Force in-memory backend for deterministic quota enforcement
    os.environ["RATE_LIMIT_BACKEND"] = "memory"
    _test_reset()
    app = create_app({
        "TESTING": True,
        "FEATURE_FLAGS": {"rate_limit_export": True},
        "FEATURE_LIMITS_JSON": overrides,
        "FEATURE_LIMITS_DEFAULTS_JSON": defaults,
    })
    # manually load registry (future: auto-load in factory)
    refresh(overrides or {}, defaults or {})
    return app


def _seed_session(client):
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 7
        sess["role"] = "admin"


def test_export_uses_tenant_override(monkeypatch):
    app = _app({"tenant:1:export_notes_csv": {"quota": 2, "per": 60}})
    events: list[tuple[str, dict[str, str]]] = []
    from core import metrics as metrics_mod
    def rec(name: str, tags: dict[str, str]):
        events.append((name, tags))
    monkeypatch.setattr(metrics_mod, "increment", rec)
    with app.test_client() as client:
        _seed_session(client)
        # two allowed
        for _ in range(2):
            r = client.get("/export/notes.csv")
            assert r.status_code == 200
            _ = r.get_data()  # consume stream
        # third should 429
    r3 = client.get("/export/notes.csv")
    _ = r3.get_data()
    assert r3.status_code == 429
    assert any(e[0]=="rate_limit.lookup" and e[1]["source"]=="tenant" for e in events)


def test_export_uses_default_when_no_tenant_entry(monkeypatch):
    app = _app(defaults={"export_tasks_csv": {"quota": 3, "per": 60}})
    events: list[tuple[str, dict[str, str]]] = []
    from core import metrics as metrics_mod
    def rec(name: str, tags: dict[str, str]):
        events.append((name, tags))
    monkeypatch.setattr(metrics_mod, "increment", rec)
    with app.test_client() as client:
        _seed_session(client)
        for i in range(3):
            r = client.get("/export/tasks.csv")
            assert r.status_code == 200
            _ = r.get_data()
        r4 = client.get("/export/tasks.csv")
        _ = r4.get_data()
        assert r4.status_code == 429
    assert any(e[0]=="rate_limit.lookup" and e[1]["source"]=="default" for e in events)


def test_lookup_metrics_emitted(monkeypatch):
    app = _app()
    events: list[tuple[str, dict[str, str]]] = []
    from core import metrics as metrics_mod
    def rec(name: str, tags: dict[str, str]):
        events.append((name, tags))
    monkeypatch.setattr(metrics_mod, "increment", rec)
    with app.test_client() as client:
        _seed_session(client)
        # fallback path
    r = client.get("/export/notes.csv")
    assert r.status_code == 200
    _ = r.get_data()
    assert any(e[0]=="rate_limit.lookup" for e in events)
