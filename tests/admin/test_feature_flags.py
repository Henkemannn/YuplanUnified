from __future__ import annotations

import pytest


def test_list_feature_flags_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.get("/admin/feature-flags")
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("error") == "unauthorized"


def test_list_feature_flags_viewer_returns_403(client_admin):
    r = client_admin.get("/admin/feature-flags", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"


def test_patch_feature_flag_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.patch("/admin/feature-flags/some-flag", json={"enabled": True})
    assert r.status_code == 401
    body = r.get_json()
    assert body.get("error") == "unauthorized"


def test_patch_feature_flag_viewer_returns_403(client_admin):
    r = client_admin.patch(
        "/admin/feature-flags/some-flag",
        json={"enabled": False},
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"
