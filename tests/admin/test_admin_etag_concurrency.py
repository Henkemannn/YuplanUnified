"""Tests for ETag/If-Match optimistic concurrency control in admin endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

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
    """DELETE /admin/users/<id> with mismatched If-Match returns 412."""
    user_id, _ = _seed_user(email="del2@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "del2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "del2", "If-Match": 'W/"wrongetag123"'}
    r = client_admin.delete(f"/admin/users/{user_id}", headers=headers)
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"
    assert r.headers.get("Content-Type") == "application/problem+json"


def test_delete_user_with_correct_etag_succeeds(client_admin):
    """DELETE /admin/users/<id> with correct If-Match succeeds."""
    user_id, updated_at = _seed_user(email="del3@ex.com")
    etag = compute_etag(user_id, updated_at)
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "del3"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "del3", "If-Match": etag}
    r = client_admin.delete(f"/admin/users/{user_id}", headers=headers)
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == str(user_id)


def test_patch_user_without_if_match_succeeds(client_admin):
    """PATCH /admin/users/<id> allows operation without If-Match (no-op allowed)."""
    user_id, _ = _seed_user(email="patch1@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "patch1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "patch1"}
    r = client_admin.patch(f"/admin/users/{user_id}", json={"role": "editor"}, headers=headers)
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    assert "ETag" in r.headers


def test_patch_user_with_wrong_etag_returns_412(client_admin):
    """PATCH /admin/users/<id> with mismatched If-Match returns 412."""
    user_id, _ = _seed_user(email="patch2@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "patch2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "patch2", "If-Match": 'W/"wrongetag456"'}
    r = client_admin.patch(f"/admin/users/{user_id}", json={"role": "editor"}, headers=headers)
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"


def test_patch_user_with_correct_etag_succeeds(client_admin):
    """PATCH /admin/users/<id> with correct If-Match succeeds."""
    user_id, updated_at = _seed_user(email="patch3@ex.com")
    etag = compute_etag(user_id, updated_at)
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "patch3"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "patch3", "If-Match": etag}
    r = client_admin.patch(f"/admin/users/{user_id}", json={"role": "editor"}, headers=headers)
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    assert "ETag" in r.headers


def test_put_user_without_if_match_succeeds(client_admin):
    """PUT /admin/users/<id> allows operation without If-Match (no-op allowed)."""
    user_id, _ = _seed_user(email="put1@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "put1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "put1"}
    r = client_admin.put(f"/admin/users/{user_id}", json={"email": "put1@ex.com", "role": "editor"}, headers=headers)
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    assert "ETag" in r.headers


def test_put_user_with_wrong_etag_returns_412(client_admin):
    """PUT /admin/users/<id> with mismatched If-Match returns 412."""
    user_id, _ = _seed_user(email="put2@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "put2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "put2", "If-Match": 'W/"wrongetag789"'}
    r = client_admin.put(f"/admin/users/{user_id}", json={"email": "put2@ex.com", "role": "editor"}, headers=headers)
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"


def test_patch_role_without_if_match_succeeds(client_admin):
    """PATCH /admin/roles/<id> allows operation without If-Match."""
    user_id, _ = _seed_user(email="role1@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "role1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "role1"}
    r = client_admin.patch(f"/admin/roles/{user_id}", json={"role": "editor"}, headers=headers)
    
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "editor"
    assert "ETag" in r.headers


def test_patch_role_with_wrong_etag_returns_412(client_admin):
    """PATCH /admin/roles/<id> with mismatched If-Match returns 412."""
    user_id, _ = _seed_user(email="role2@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "role2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "role2", "If-Match": 'W/"wrongrole123"'}
    r = client_admin.patch(f"/admin/roles/{user_id}", json={"role": "editor"}, headers=headers)
    
    assert r.status_code == 412
    data = r.get_json()
    assert data["title"] == "Precondition Failed"


def test_etag_response_header_format(client_admin):
    """ETag response header should be in correct weak ETag format."""
    user_id, _ = _seed_user(email="etag@ex.com")
    
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "etag"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "etag"}
    r = client_admin.patch(f"/admin/users/{user_id}", json={"role": "editor"}, headers=headers)
    
    assert r.status_code == 200
    etag = r.headers.get("ETag")
    assert etag is not None
    assert etag.startswith('W/"')
    assert etag.endswith('"')
    assert len(etag) > 10  # Should have meaningful hash
