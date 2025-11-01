from __future__ import annotations

from core.db import get_session
from core.models import User, TenantFeatureFlag


def _seed_users():
    db = get_session()
    try:
        # tenant 1
        if not db.query(User).filter_by(tenant_id=1, email="u1@example.com").first():
            db.add(User(tenant_id=1, email="u1@example.com", role="viewer", password_hash="!"))
        if not db.query(User).filter_by(tenant_id=1, email="u2@example.com").first():
            db.add(User(tenant_id=1, email="u2@example.com", role="editor", password_hash="!"))
        # another tenant to ensure scoping
        if not db.query(User).filter_by(tenant_id=2, email="other@example.com").first():
            db.add(User(tenant_id=2, email="other@example.com", role="viewer", password_hash="!"))
        db.commit()
    finally:
        db.close()


def _seed_flags():
    db = get_session()
    try:
        if not db.query(TenantFeatureFlag).filter_by(tenant_id=1, name="activate-search").first():
            db.add(TenantFeatureFlag(tenant_id=1, name="activate-search", enabled=True, notes="Activated"))
        if not db.query(TenantFeatureFlag).filter_by(tenant_id=1, name="beta-preview").first():
            db.add(TenantFeatureFlag(tenant_id=1, name="beta-preview", enabled=False, notes="Preview"))
        db.commit()
    finally:
        db.close()


def test_users_list_returns_items_and_total(client_admin):
    _seed_users()
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r = client_admin.get("/admin/users", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert set(body.keys()) >= {"items", "total"}
    emails = [it["email"] for it in body["items"]]
    assert "u1@example.com" in emails and "u2@example.com" in emails
    assert "other@example.com" not in emails


def test_roles_list_returns_items_and_total(client_admin):
    _seed_users()
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r = client_admin.get("/admin/roles", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert set(body.keys()) >= {"items", "total"}
    emails = [it["email"] for it in body["items"]]
    assert "u1@example.com" in emails and "u2@example.com" in emails


def test_feature_flags_list_supports_q_filter(client_admin):
    _seed_flags()
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r = client_admin.get("/admin/feature-flags?q=act", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    keys = [it["key"] for it in body["items"]]
    assert "activate-search" in keys
    assert "beta-preview" not in keys
