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


@pytest.mark.xfail(strict=False, reason="Phase-2: validation not implemented")
def test_patch_roles_422_role_not_in_enum(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/roles/123", json={"role": "owner"}, headers=headers
    )
    assert r.status_code == 422


@pytest.mark.xfail(strict=False, reason="Phase-2: validation not implemented")
def test_patch_roles_422_additional_properties(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/roles/123", json={"role": "viewer", "other": True}, headers=headers
    )
    assert r.status_code == 422


@pytest.mark.xfail(strict=False, reason="Phase-2: not-found not implemented")
def test_patch_roles_404_unknown_user_id(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/roles/nonexistent-user", json={"role": "viewer"}, headers=headers
    )
    assert r.status_code == 404
