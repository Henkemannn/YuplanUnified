"""Tests for ETag/If-Match optimistic concurrency control in admin endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.concurrency import compute_etag
from core.db import get_session
from core.models import TenantFeatureFlag, User


def _seed_user(tenant_id: int = 1, email: str = "test@example.com", role: str = "viewer"):
    """Helper to seed a user with updated_at timestamp."""
    db = get_session()
    try:
        u = db.query(User).filter_by(tenant_id=tenant_id, email=email).first()
        if not u:
            u = User(tenant_id=tenant_id, email=email, role=role, password_hash="!")
            u.updated_at = datetime.now(UTC)
            db.add(u)
            db.commit()
            db.refresh(u)
        return u.id, u.updated_at
    finally:
        db.close()


def _seed_feature_flag(tenant_id: int = 1, name: str = "test_flag", enabled: bool = True):
    """Helper to seed a feature flag with updated_at timestamp."""
    db = get_session()
    try:
        f = db.query(TenantFeatureFlag).filter_by(tenant_id=tenant_id, name=name).first()
        if not f:
            f = TenantFeatureFlag(tenant_id=tenant_id, name=name, enabled=enabled, notes="Test")
            f.updated_at = datetime.now(UTC)
            db.add(f)
            db.commit()
            db.refresh(f)
        return f.updated_at
    finally:
        db.close()


def test_delete_user_without_if_match_returns_400(client_admin):
    """DELETE /admin/users/<id> requires If-Match header - returns 400 if missing."""
    user_id, _ = _seed_user(email="del1@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "del1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "del1"}
    r = client_admin.delete(f"/admin/users/{user_id}", headers=headers)
    
    assert r.status_code == 400
    data = r.get_json()
    assert data["type"] == "about:blank"
    assert data["title"] == "Bad Request"
    assert data["status"] == 400
    assert "If-Match" in data["detail"]
    assert r.headers.get("Content-Type") == "application/problem+json"
    
    # Verify invalid_params includes If-Match
    invalid_params = data.get("invalid_params", [])
    assert any(p.get("name") == "If-Match" for p in invalid_params)


def test_delete_user_with_wrong_etag_returns_412(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "test_delete_use"
    headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "test_delete_use",
        "If-Match": 'W/"wrongetag123"'
    }
    r = client_admin.delete(f"/admin/users/{user_id}", headers=headers)
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["type"] == "about:blank"
    assert data["title"] == "Precondition Failed"
    assert data["status"] == 412
    assert "modified" in data["detail"].lower()
    assert r.headers.get("Content-Type") == "application/problem+json"


def test_delete_user_with_correct_etag_succeeds(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "test_delete_use"
    headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "test_delete_use",
    }
    r = client_admin.delete(f"/admin/users/{user_id}", headers=headers)
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == str(user_id)
    assert "deleted_at" in data


def test_patch_user_without_if_match_succeeds(client_admin):
    """PATCH /admin/users/<id> allows operation without If-Match (no-op allowed)."""
    user_id, _ = _seed_user(email="patch1@ex.com")
    
    with client_admin.session_transaction() as sess:
    
        sess["CSRF_TOKEN"] = "delete_use"
    
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "delete_use"}
    r = client_admin.patch(
        f"/admin/users/{user_id}",
        json={"role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    # Response should include ETag header
    assert "ETag" in r.headers


def test_patch_user_with_wrong_etag_returns_412(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "test_patch_user"
    headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "test_patch_user",
    }
    r = client_admin.patch(
        f"/admin/users/{user_id}",
        json={"role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"
    assert r.headers.get("Content-Type") == "application/problem+json"


def test_patch_user_with_correct_etag_succeeds(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "test_patch_user"
    headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "test_patch_user",
    }
    r = client_admin.patch(
        f"/admin/users/{user_id}",
        json={"role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    assert "ETag" in r.headers


def test_put_user_without_if_match_succeeds(client_admin):
    """PUT /admin/users/<id> allows operation without If-Match (no-op allowed)."""
    user_id, _ = _seed_user(email="put1@ex.com")
    
    with client_admin.session_transaction() as sess:
    
        sess["CSRF_TOKEN"] = "patch_user"
    
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "patch_user"}
    r = client_admin.put(
        f"/admin/users/{user_id}",
        json={"email": "put1@ex.com", "role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    assert "ETag" in r.headers


def test_put_user_with_wrong_etag_returns_412(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "test_put_user_w"
    headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "test_put_user_w",
    }
    r = client_admin.put(
        f"/admin/users/{user_id}",
        json={"email": "put2@ex.com", "role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"


def test_patch_role_without_if_match_succeeds(client_admin):
    """PATCH /admin/roles/<id> allows operation without If-Match."""
    user_id, _ = _seed_user(email="role1@ex.com")
    
    with client_admin.session_transaction() as sess:
    
        sess["CSRF_TOKEN"] = "put_user_w"
    
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "put_user_w"}
    r = client_admin.patch(
        f"/admin/roles/{user_id}",
        json={"role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    assert "ETag" in r.headers


def test_patch_role_with_wrong_etag_returns_412(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "test_patch_role"
    headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "test_patch_role",
    }
    r = client_admin.patch(
        f"/admin/roles/{user_id}",
        json={"role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"


def test_patch_feature_flag_without_if_match_succeeds(client_admin):
    """PATCH /admin/feature-flags/<key> allows operation without If-Match."""
    _ = _seed_feature_flag(name="flag1")
    
    with client_admin.session_transaction() as sess:
    
        sess["CSRF_TOKEN"] = "patch_role"
    
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "patch_role"}
    r = client_admin.patch(
        "/admin/feature-flags/flag1",
        json={"enabled": False},
        headers=headers
    )
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["enabled"] is False
    assert "ETag" in r.headers


def test_patch_feature_flag_with_wrong_etag_returns_412(client_admin):
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "test_patch_feat"
    headers = {
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "test_patch_feat",
    }
    r = client_admin.patch(
        "/admin/feature-flags/flag2",
        json={"enabled": False},
        headers=headers
    )
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"


def test_etag_response_header_format(client_admin):
    """ETag response header should be in correct weak ETag format."""
    user_id, _ = _seed_user(email="etag@ex.com")
    
    with client_admin.session_transaction() as sess:
    
        sess["CSRF_TOKEN"] = "patch_feat"
    
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "patch_feat"}
    r = client_admin.patch(
        f"/admin/users/{user_id}",
        json={"role": "editor"},
        headers=headers
    )
    
    assert r.status_code == 200
    etag = r.headers.get("ETag")
    assert etag is not None
    assert etag.startswith('W/"')
    assert etag.endswith('"')
    assert len(etag) > 10  # Should have meaningful hash
