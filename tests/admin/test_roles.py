from __future__ import annotations

import pytest


def test_list_roles_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.get("/admin/roles")
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("error") == "unauthorized"


def test_list_roles_viewer_returns_403(client_admin):
    r = client_admin.get("/admin/roles", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"


def test_patch_roles_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.patch("/admin/roles/123", json={"role": "editor"})
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("error") == "unauthorized"


def test_patch_roles_viewer_returns_403(client_admin):
    r = client_admin.patch(
        "/admin/roles/123",
        json={"role": "viewer"},
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"


def test_patch_roles_csrf_missing_blocks_mutation(client_admin):
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1"}
    r = client_admin.patch(
        "/admin/roles/123", json={"role": "editor"}, headers=headers
    )
    assert r.status_code in (401, 403)
    body = r.get_json()
    assert body.get("error") in ("unauthorized", "forbidden")
    if r.status_code == 403:
        assert body.get("required_role") == "admin"


def test_patch_roles_csrf_invalid_token_still_blocked(client_admin):
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/roles/123", json={"role": "viewer"}, headers=headers
    )
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"


def test_patch_roles_admin_missing_or_invalid_csrf_returns_401(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.patch("/admin/roles/123", json={"role": "viewer"}, headers=headers)
    assert r1.status_code == 401
    headers["X-CSRF-Token"] = "bogus"
    r2 = client_admin.patch("/admin/roles/123", json={"role": "viewer"}, headers=headers)
    assert r2.status_code == 401


def test_patch_roles_admin_blocked_by_missing_or_invalid_csrf(client_admin):
    headers_missing = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.patch(
        "/admin/roles/123", json={"role": "viewer"}, headers=headers_missing
    )
    assert r1.status_code == 401
    headers_invalid = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "bogus"}
    r2 = client_admin.patch(
        "/admin/roles/123", json={"role": "viewer"}, headers=headers_invalid
    )
    assert r2.status_code == 401


def test_patch_roles_422_role_not_in_enum(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tr1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tr1"}
    r = client_admin.patch(
        "/admin/roles/123", json={"role": "owner"}, headers=headers
    )
    assert r.status_code == 422
    body = r.get_json()
    ips = body.get("invalid_params") or []
    assert any(p.get("name") == "role" for p in ips)


def test_patch_roles_422_additional_properties(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tr2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tr2"}
    r = client_admin.patch(
        "/admin/roles/123", json={"role": "viewer", "other": True}, headers=headers
    )
    assert r.status_code == 422
    body = r.get_json()
    ips = body.get("invalid_params") or []
    assert any((p.get("name") in ("other", "unknown")) and p.get("reason") == "additional_properties_not_allowed" for p in ips)


def test_patch_roles_404_unknown_user_id(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tr3"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tr3"}
    r = client_admin.patch(
        "/admin/roles/nonexistent-user", json={"role": "viewer"}, headers=headers
    )
    assert r.status_code == 404


def test_patch_roles_happy_path_persists_change_and_idempotent(client_admin):
    # Seed a user with role viewer in tenant 1
    from core.db import get_session
    from core.models import User

    db = get_session()
    try:
        u = User(tenant_id=1, email="rolepatch1@example.com", password_hash="x", role="viewer")
        db.add(u)
        db.commit()
        db.refresh(u)
        uid = str(u.id)
    finally:
        db.close()

    # Prepare CSRF for admin
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tokR1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tokR1"}

    # Change role to editor
    r1 = client_admin.patch(f"/admin/roles/{uid}", json={"role": "editor"}, headers=headers)
    assert r1.status_code == 200
    body1 = r1.get_json()
    assert body1.get("id") == uid
    assert body1.get("email") == "rolepatch1@example.com"
    assert body1.get("role") == "editor"
    assert isinstance(body1.get("updated_at"), str) and "T" in body1.get("updated_at")

    # Idempotent call with same role
    r2 = client_admin.patch(f"/admin/roles/{uid}", json={"role": "editor"}, headers=headers)
    assert r2.status_code == 200
    body2 = r2.get_json()
    assert body2.get("role") == "editor"
    # Verify persisted in DB
    db2 = get_session()
    try:
        from core.models import User as _User
        persisted = db2.query(_User).filter_by(id=int(uid), tenant_id=1).first()
        assert persisted is not None
        assert persisted.role == "editor"
    finally:
        db2.close()
