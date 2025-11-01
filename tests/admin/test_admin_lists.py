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


def test_pagination_stub_header_present_on_valid_params(client_admin):
    _seed_users()
    _seed_flags()
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

    for path in ("/admin/users", "/admin/roles", "/admin/feature-flags"):
        r = client_admin.get(f"{path}?page=1&size=20", headers=headers)
        assert r.status_code == 200
        assert r.headers.get("X-Pagination-Stub") == "true"
        body = r.get_json()
        assert set(body.keys()) >= {"items", "total"}


def test_pagination_stub_coerces_and_sets_header(client_admin):
    _seed_users()
    _seed_flags()
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

    # Out of bounds should be coerced and still set header
    for path in ("/admin/users", "/admin/roles", "/admin/feature-flags"):
        r1 = client_admin.get(f"{path}?page=0&size=0", headers=headers)
        assert r1.status_code == 200
        assert r1.headers.get("X-Pagination-Stub") == "true"
        body1 = r1.get_json()
        assert set(body1.keys()) >= {"items", "total"}

    # Specific second combo for feature-flags per prompt
    r2 = client_admin.get("/admin/feature-flags?page=2&size=5", headers=headers)
    assert r2.status_code == 200
    assert r2.headers.get("X-Pagination-Stub") == "true"
    body2 = r2.get_json()
    assert set(body2.keys()) >= {"items", "total"}


def test_users_list_supports_q_filter(client_admin):
    # Seed specific users for tenant 1
    db = get_session()
    try:
        if not db.query(User).filter_by(tenant_id=1, email="a@ex").first():
            db.add(User(tenant_id=1, email="a@ex", role="viewer", password_hash="!"))
        if not db.query(User).filter_by(tenant_id=1, email="b@sample").first():
            db.add(User(tenant_id=1, email="b@sample", role="editor", password_hash="!"))
        db.commit()
    finally:
        db.close()

    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    # Lowercase query (specific substring)
    r1 = client_admin.get("/admin/users?q=a@ex", headers=headers)
    assert r1.status_code == 200
    body1 = r1.get_json()
    emails1 = [it["email"] for it in body1["items"]]
    assert emails1 == ["a@ex"]
    assert body1["total"] == 1

    # Uppercase query should behave the same (case-insensitive)
    r2 = client_admin.get("/admin/users?q=A@EX", headers=headers)
    assert r2.status_code == 200
    body2 = r2.get_json()
    emails2 = [it["email"] for it in body2["items"]]
    assert emails2 == ["a@ex"]
    assert body2["total"] == 1
