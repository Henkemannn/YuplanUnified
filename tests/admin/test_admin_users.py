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
