from __future__ import annotations

import hashlib

from core.db import get_session
from core.models import User

from ._problem_utils import assert_problem


def _etag_for_user(user_id: int) -> str:
    db = get_session()
    try:
        row = db.query(User).filter_by(id=user_id).first()
        ts = getattr(row, "updated_at", None)
        ts_iso = ts.isoformat() if ts is not None else ""
        raw = f"{user_id}:{ts_iso}".encode()
        return 'W/"' + hashlib.sha1(raw).hexdigest() + '"'
    finally:
        db.close()


def _seed_two_users(tenant_id: int = 1):
    db = get_session()
    try:
        if not db.query(User).filter_by(tenant_id=tenant_id, email="u1@example.com").first():
            db.add(User(tenant_id=tenant_id, email="u1@example.com", role="viewer", password_hash="!"))
        if not db.query(User).filter_by(tenant_id=tenant_id, email="u2@example.com").first():
            db.add(User(tenant_id=tenant_id, email="u2@example.com", role="editor", password_hash="!"))
        db.commit()
        # Return their ids
        u1 = db.query(User).filter_by(tenant_id=tenant_id, email="u1@example.com").first()
        u2 = db.query(User).filter_by(tenant_id=tenant_id, email="u2@example.com").first()
        return (u1.id if u1 else None, u2.id if u2 else None)
    finally:
        db.close()


def test_soft_delete_and_list_filtering(client_admin):
    # Arrange: seed and capture ids
    u1_id, u2_id = _seed_two_users(tenant_id=1)
    assert u1_id is not None and u2_id is not None

    # Prime CSRF for admin
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "sd1"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "sd1"}

    # Delete u1
    # Include concurrency precondition
    headers_del = dict(headers)
    headers_del["If-Match"] = _etag_for_user(int(u1_id))
    r_del = client_admin.delete(f"/admin/users/{u1_id}", headers=headers_del)
    assert r_del.status_code == 204
    # No content on success
    assert (r_del.data is None) or (r_del.data == b"")

    # Lists exclude deleted
    r_users = client_admin.get("/admin/users", headers=headers)
    assert r_users.status_code == 200
    emails_users = [it["email"] for it in r_users.get_json()["items"]]
    assert "u1@example.com" not in emails_users
    assert "u2@example.com" in emails_users

    r_roles = client_admin.get("/admin/roles", headers=headers)
    assert r_roles.status_code == 200
    emails_roles = [it["email"] for it in r_roles.get_json()["items"]]
    assert "u1@example.com" not in emails_roles
    assert "u2@example.com" in emails_roles

    # Idempotency: deleting again yields 404
    r_del2 = client_admin.delete(f"/admin/users/{u1_id}", headers=headers)
    assert_problem(r_del2, 404, "Not Found")
