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
