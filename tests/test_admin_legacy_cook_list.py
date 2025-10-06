from __future__ import annotations

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from core.app_factory import create_app
from core.db import get_session
from core.models import Tenant, User


@pytest.fixture()
def app():
    return create_app({"TESTING": True, "SECRET_KEY": "test"})


@pytest.fixture()
def client(app: Flask):
    return app.test_client()


def _ensure_tenant(name: str) -> int:
    db = get_session()
    try:
        t = db.query(Tenant).filter_by(name=name).first()
        if not t:
            t = Tenant(name=name)
            db.add(t); db.commit(); db.refresh(t)
        return t.id
    finally:
        db.close()


def _ensure_user(email: str, role: str, tenant_id: int) -> None:
    db = get_session()
    try:
        u = db.query(User).filter_by(email=email).first()
        if not u:
            u = User(tenant_id=tenant_id, email=email, password_hash=generate_password_hash("pw"), role=role, unit_id=None)
            db.add(u); db.commit(); db.refresh(u)
    finally:
        db.close()


def _login(client, email: str):
    return client.post("/auth/login", json={"email": email, "password": "pw"})


def _enable_flag(client, tenant_id: int):
    # superuser toggles flag for specified tenant
    rv = client.post("/admin/feature_flags", json={"name": "allow_legacy_cook_create", "enabled": True, "tenant_id": tenant_id})
    assert rv.status_code == 200


def test_list_legacy_cook_requires_admin(client):
    # 401 no login
    r = client.get("/admin/flags/legacy-cook")
    assert r.status_code == 401

    # setup tenant + users
    tid = _ensure_tenant("FlagT1")
    _ensure_user("viewer1@example.com", "viewer", tid)
    _ensure_user("admin1@example.com", "admin", tid)

    # login as viewer -> 403
    _login(client, "viewer1@example.com")
    r = client.get("/admin/flags/legacy-cook")
    assert r.status_code == 403
    body = r.get_json()
    # Central forbidden handler returns generic message when roles tuple used; required_role may be absent
    assert body["ok"] is False and body["error"] == "forbidden"


def test_list_legacy_cook_happy(client):
    # Setup tenants and enable flag on one
    tid1 = _ensure_tenant("FlagHT1")
    tid2 = _ensure_tenant("FlagHT2")
    _ensure_user("root@example.com", "superuser", tid1)
    _ensure_user("admin_ht1@example.com", "admin", tid1)

    _login(client, "root@example.com")
    _enable_flag(client, tid1)

    # Login as admin (tenant1) to list
    _login(client, "admin_ht1@example.com")
    r = client.get("/admin/flags/legacy-cook")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    tenants = body["tenants"]
    assert isinstance(tenants, list)
    ids = {int(t["id"]) for t in tenants}
    assert tid1 in ids
    assert tid2 not in ids
