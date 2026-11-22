from __future__ import annotations

import os
from typing import Any

from flask import Flask

from core.app_factory import create_app
from core.limit_registry import refresh
from core.rate_limiter import _test_reset


def _app(
    overrides: dict[str, Any] | str | None = None, defaults: dict[str, Any] | str | None = None
) -> Flask:
    # Force in-memory backend for deterministic quota enforcement
    os.environ["RATE_LIMIT_BACKEND"] = "memory"
    _test_reset()
    app = create_app(
        {
            "TESTING": True,
            "FEATURE_FLAGS": {"rate_limit_export": True},
            "FEATURE_LIMITS_JSON": overrides,
            "FEATURE_LIMITS_DEFAULTS_JSON": defaults,
        }
    )
    # manually load registry (future: auto-load in factory)
    refresh(overrides or {}, defaults or {})
    return app


def _seed_session(client):
    from core.db import get_session
    from core.models import Site, User
    from sqlalchemy import text

    db = get_session()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if user is None:
            user = User(id=1, tenant_id=1, username="rate-limit-admin", email="rate-limit-admin@example.test", password_hash="!", role="admin", is_active=True, auth_version=1)
            db.add(user)
        else:
            user.tenant_id = 1
            user.role = "admin"
            user.is_active = True
            user.auth_version = 1
        db.commit()
        if db.get(Site, "rate-registry-site") is None:
            db.add(Site(id="rate-registry-site", tenant_id=1, name="Rate Registry Site"))
            db.commit()
        db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS kitchen_user_sites "
                "(user_id INTEGER, tenant_id INTEGER, site_id TEXT)"
            )
        )
        db.execute(
            text(
                "INSERT OR REPLACE INTO kitchen_user_sites(user_id, tenant_id, site_id) "
                "VALUES (1, 1, 'rate-registry-site')"
            )
        )
        db.commit()
    finally:
        db.close()
    with client.session_transaction() as sess:
        sess["tenant_id"] = 1
        sess["user_id"] = 1
        sess["auth_version"] = 1
        sess["role"] = "admin"
        sess["site_id"] = "rate-registry-site"


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
    assert "Retry-After" in r3.headers
    assert int(r3.headers["Retry-After"]) >= 0
    data = r3.get_json()
    assert data["status"] == 429
    assert data["type"].endswith("/rate_limited")
    assert any(e[0] == "rate_limit.lookup" and e[1]["source"] == "tenant" for e in events)


def test_export_uses_default_when_no_tenant_entry(monkeypatch):
    app = _app(defaults={"export_notes_csv": {"quota": 3, "per": 60}})
    events: list[tuple[str, dict[str, str]]] = []
    from core import metrics as metrics_mod

    def rec(name: str, tags: dict[str, str]):
        events.append((name, tags))

    monkeypatch.setattr(metrics_mod, "increment", rec)
    with app.test_client() as client:
        _seed_session(client)
        for _i in range(3):
            r = client.get("/export/notes.csv")
            assert r.status_code == 200
            _ = r.get_data()
        r4 = client.get("/export/notes.csv")
        _ = r4.get_data()
        assert r4.status_code == 429
        assert "Retry-After" in r4.headers
        assert r4.get_json()["type"].endswith("/rate_limited")
    assert any(e[0] == "rate_limit.lookup" and e[1]["source"] == "default" for e in events)


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
    assert any(e[0] == "rate_limit.lookup" for e in events)
