from __future__ import annotations

import pytest
from ._problem_utils import assert_problem


def test_list_feature_flags_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.get("/admin/feature-flags")
    assert_problem(r, 401, "Unauthorized")


def test_list_feature_flags_viewer_returns_403(client_admin):
    r = client_admin.get("/admin/feature-flags", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    b = assert_problem(r, 403, "Forbidden")
    assert b.get("required_role") == "admin"
    inv = b.get("invalid_params") or []
    assert any(p.get("name") == "required_role" for p in inv)


def test_patch_feature_flag_unauth_returns_401(client_no_tenant):
    r = client_no_tenant.patch("/admin/feature-flags/some-flag", json={"enabled": True})
    assert_problem(r, 401, "Unauthorized")


def test_patch_feature_flag_viewer_returns_403(client_admin):
    r = client_admin.patch(
        "/admin/feature-flags/some-flag",
        json={"enabled": False},
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    b = assert_problem(r, 403, "Forbidden")
    assert b.get("required_role") == "admin"
    inv = b.get("invalid_params") or []
    assert any(p.get("name") == "required_role" for p in inv)


def test_patch_feature_flag_csrf_missing_blocks_mutation(client_admin):
    # Without CSRF token: ensure forbidden for non-admin
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": True}, headers=headers
    )
    assert r.status_code in (401, 403)
    b = assert_problem(r)
    if r.status_code == 403:
        assert b.get("required_role") == "admin"
        inv = b.get("invalid_params") or []
        assert any(p.get("name") == "required_role" for p in inv)


def test_patch_feature_flag_csrf_invalid_token_still_blocked(client_admin):
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1", "X-CSRF-Token": "fake"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": False}, headers=headers
    )
    b = assert_problem(r, 403, "Forbidden")
    assert b.get("required_role") == "admin"
    inv = b.get("invalid_params") or []
    assert any(p.get("name") == "required_role" for p in inv)


def test_patch_feature_flag_admin_missing_or_invalid_csrf_returns_401(client_admin):
    # Admin without CSRF token
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.patch("/admin/feature-flags/some-flag", json={"enabled": True}, headers=headers)
    assert_problem(r1, 401, "Unauthorized")
    # Admin with bogus token
    headers["X-CSRF-Token"] = "bogus"
    r2 = client_admin.patch("/admin/feature-flags/some-flag", json={"enabled": False}, headers=headers)
    assert_problem(r2, 401, "Unauthorized")


def test_patch_feature_flag_admin_blocked_by_missing_or_invalid_csrf(client_admin):
    headers_missing = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": True}, headers=headers_missing
    )
    assert_problem(r1, 401, "Unauthorized")
    headers_invalid = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "bogus"}
    r2 = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": False}, headers=headers_invalid
    )
    assert_problem(r2, 401, "Unauthorized")


def test_patch_feature_flag_happy_path_persists_enabled_and_notes(client_admin, app_session):
    # Seed a feature-flag for tenant 1
    from core.db import get_session
    from core.models import TenantFeatureFlag
    db = get_session()
    try:
        if not db.query(TenantFeatureFlag).filter_by(tenant_id=1, name="some-flag").first():
            db.add(TenantFeatureFlag(tenant_id=1, name="some-flag", enabled=False))
            db.commit()
    finally:
        db.close()
    # Admin + CSRF
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "pfl1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "pfl1"}
    # Toggle enabled and update notes
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": True, "notes": "Activated"}, headers=headers
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("key") == "some-flag"
    assert body.get("enabled") is True
    assert body.get("notes") == "Activated"
    # updated_at is optional but if present should be a string
    if body.get("updated_at") is not None:
        assert isinstance(body["updated_at"], str)

def test_patch_feature_flag_422_enabled_wrong_type(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tfl1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tfl1"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": "yes"}, headers=headers
    )
    assert_problem(r, 422, "Validation error")


def test_patch_feature_flag_422_notes_too_long(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tfl2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tfl2"}
    notes = "x" * 501
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"notes": notes}, headers=headers
    )
    assert_problem(r, 422, "Validation error")


def test_patch_feature_flag_422_additional_properties(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tfl3"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tfl3"}
    r = client_admin.patch(
        "/admin/feature-flags/some-flag", json={"enabled": True, "other": 1}, headers=headers
    )
    assert_problem(r, 422, "Validation error")


def test_patch_feature_flag_404_unknown_key(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "tfl4"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "tfl4"}
    r = client_admin.patch(
        "/admin/feature-flags/does-not-exist", json={"enabled": True}, headers=headers
    )
    assert_problem(r, 404, "Not Found")
