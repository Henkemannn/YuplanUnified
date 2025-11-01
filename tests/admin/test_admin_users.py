from __future__ import annotations

import pytest


def test_get_users_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.get("/admin/users")
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("error") == "unauthorized"


def test_get_users_viewer_returns_403(client_admin):
    r = client_admin.get("/admin/users", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    # Central handler enriches with required_role
    assert body.get("required_role") == "admin"


def test_post_users_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.post("/admin/users", json={"email": "u@example.com", "role": "viewer"})
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("error") == "unauthorized"


def test_post_users_viewer_returns_403(client_admin):
    r = client_admin.post(
        "/admin/users",
        json={"email": "u@example.com", "role": "viewer"},
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"


def test_post_users_csrf_missing_blocks_mutation(client_admin):
    # Without CSRF token: still blocked by RBAC for non-admin
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1"}
    r = client_admin.post(
        "/admin/users", json={"email": "v@example.com", "role": "viewer"}, headers=headers
    )
    assert r.status_code in (401, 403)
    body = r.get_json()
    assert body.get("error") in ("unauthorized", "forbidden")
    if r.status_code == 403:
        assert body.get("required_role") == "admin"


def test_post_users_csrf_invalid_token_still_blocked_by_rbac(client_admin):
    # Fake token does not bypass RBAC; expect 403 for viewer
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.post(
        "/admin/users", json={"email": "v2@example.com", "role": "viewer"}, headers=headers
    )
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"


def test_post_users_admin_missing_or_invalid_csrf_returns_401(client_admin):
    # Admin without CSRF token
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.post("/admin/users", json={"email": "a@example.com", "role": "viewer"}, headers=headers)
    assert r1.status_code == 401
    # Admin with bogus token
    headers["X-CSRF-Token"] = "bogus"
    r2 = client_admin.post("/admin/users", json={"email": "b@example.com", "role": "viewer"}, headers=headers)
    assert r2.status_code == 401


def test_post_users_admin_blocked_without_or_invalid_csrf(client_admin):
    # Admin without CSRF should be blocked by CSRF enforcement
    admin_headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.post(
        "/admin/users", json={"email": "a@example.com", "role": "viewer"}, headers=admin_headers
    )
    assert r1.status_code == 401
    body1 = r1.get_json()
    assert body1.get("status") == 401 or body1.get("error") == "unauthorized"
    # With bogus token still blocked
    admin_headers2 = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "bogus"}
    r2 = client_admin.post(
        "/admin/users", json={"email": "a2@example.com", "role": "viewer"}, headers=admin_headers2
    )
    assert r2.status_code == 401


def test_post_users_happy_path_creates_user_and_returns_201(client_admin):
    # Arrange admin + CSRF
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "u1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "u1"}
    # Valid payload
    payload = {"email": "new@example.com", "role": "viewer"}
    r = client_admin.post("/admin/users", json=payload, headers=headers)
    assert r.status_code == 201
    body = r.get_json()
    assert isinstance(body, dict)
    # Minimal shape checks
    assert body.get("email") == payload["email"]
    assert body.get("role") == payload["role"]
    assert body.get("id") is not None and str(body.get("id")) != ""


def test_post_users_duplicate_email_returns_422(client_admin):
    # Admin + CSRF
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "u2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "u2"}
    payload = {"email": "dup@example.com", "role": "viewer"}
    r1 = client_admin.post("/admin/users", json=payload, headers=headers)
    assert r1.status_code == 201
    # Post again with same email
    r2 = client_admin.post("/admin/users", json=payload, headers=headers)
    assert r2.status_code == 422
    body = r2.get_json()
    ips = body.get("invalid_params") or []
    assert any(p.get("name") == "email" and p.get("reason") == "duplicate" for p in ips)

def test_post_users_422_invalid_email(client_admin):
    # Ensure CSRF passes by priming session token
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "t1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "t1"}
    r = client_admin.post(
        "/admin/users", json={"email": "not-an-email", "role": "viewer"}, headers=headers
    )
    assert r.status_code == 422
    body = r.get_json()
    assert isinstance(body, dict)
    ips = body.get("invalid_params") or []
    assert any(p.get("name") == "email" for p in ips)


def test_post_users_422_invalid_role_enum(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "t2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "t2"}
    r = client_admin.post(
        "/admin/users", json={"email": "ok@example.com", "role": "owner"}, headers=headers
    )
    assert r.status_code == 422
    body = r.get_json()
    ips = body.get("invalid_params") or []
    assert any(p.get("name") == "role" and p.get("reason") == "invalid_enum" for p in ips)
    # Optional: if server includes allowed list
    if any(p.get("name") == "role" and p.get("allowed") for p in ips):
        assert set(next(p.get("allowed") for p in ips if p.get("name") == "role")) >= {"admin","editor","viewer"}


def test_post_users_422_additional_properties(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "t3"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "t3"}
    r = client_admin.post(
        "/admin/users", json={"email": "ok@example.com", "role": "viewer", "extra": True}, headers=headers
    )
    assert r.status_code == 422
    body = r.get_json()
    ips = body.get("invalid_params") or []
    assert any((p.get("name") in ("extra", "unknown")) and p.get("reason") == "additional_properties_not_allowed" for p in ips)
