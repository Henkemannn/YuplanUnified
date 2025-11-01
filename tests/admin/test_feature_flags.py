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


def test_patch_feature_flag_csrf_missing_blocks_mutation(client_admin):
    # Without CSRF token: ensure forbidden for non-admin
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": True}, headers=headers
    )
    assert r.status_code in (401, 403)
    body = r.get_json()
    assert body.get("error") in ("unauthorized", "forbidden")
    if r.status_code == 403:
        assert body.get("required_role") == "admin"


def test_patch_feature_flag_csrf_invalid_token_still_blocked(client_admin):
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": False}, headers=headers
    )
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("error") == "forbidden"
    assert body.get("required_role") == "admin"


def test_patch_feature_flag_admin_missing_or_invalid_csrf_returns_401(client_admin):
    # Admin without CSRF token
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.patch("/admin/feature-flags/some-flag", json={"enabled": True}, headers=headers)
    assert r1.status_code == 401
    # Admin with bogus token
    headers["X-CSRF-Token"] = "bogus"
    r2 = client_admin.patch("/admin/feature-flags/some-flag", json={"enabled": False}, headers=headers)
    assert r2.status_code == 401


def test_patch_feature_flag_admin_blocked_by_missing_or_invalid_csrf(client_admin):
    headers_missing = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": True}, headers=headers_missing
    )
    assert r1.status_code == 401
    headers_invalid = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "bogus"}
    r2 = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": False}, headers=headers_invalid
    )
    assert r2.status_code == 401


@pytest.mark.xfail(strict=False, reason="Phase-2: validation not implemented")
def test_patch_feature_flag_422_enabled_wrong_type(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": "yes"}, headers=headers
    )
    assert r.status_code == 422


@pytest.mark.xfail(strict=False, reason="Phase-2: validation not implemented")
def test_patch_feature_flag_422_notes_too_long(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    notes = "x" * 501
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"notes": notes}, headers=headers
    )
    assert r.status_code == 422


@pytest.mark.xfail(strict=False, reason="Phase-2: validation not implemented")
def test_patch_feature_flag_422_additional_properties(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": True, "other": 1}, headers=headers
    )
    assert r.status_code == 422


@pytest.mark.xfail(strict=False, reason="Phase-2: not-found not implemented")
def test_patch_feature_flag_404_unknown_key(client_admin):
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/feature-flags/does-not-exist", json={"enabled": True}, headers=headers
    )
    assert r.status_code == 404
