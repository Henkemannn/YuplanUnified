from __future__ import annotations

from core.db import get_session
from core.models import User


def _seed_three_users(tenant_id: int = 1):
    from datetime import UTC, datetime
    db = get_session()
    try:
        emails = ["ux1@example.com", "ux2@example.com", "ux3@example.com"]
        for i, em in enumerate(emails, start=1):
            if not db.query(User).filter_by(tenant_id=tenant_id, email=em).first():
                role = "admin" if i == 1 else ("editor" if i == 2 else "viewer")
                u = User(tenant_id=tenant_id, email=em, role=role, password_hash="!")
                u.updated_at = datetime.now(UTC)
                db.add(u)
        db.commit()
        rows = db.query(User).filter(User.tenant_id == tenant_id, User.email.in_(emails)).all()
        return {r.email: (r.id, r.updated_at) for r in rows}
    finally:
        db.close()


def test_users_deleted_total_header_present(client_admin):
    # Arrange: seed and soft-delete one user in tenant 1
    from core.concurrency import compute_etag
    ids = _seed_three_users(tenant_id=1)
    assert len(ids) == 3
    del_id, del_updated_at = ids["ux1@example.com"]

    # CSRF prime for DELETE (mutating admin op)
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "hdr1"
    etag = compute_etag(del_id, del_updated_at)
    headers_admin = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "hdr1", "If-Match": etag}

    r_del = client_admin.delete(f"/admin/users/{del_id}", headers=headers_admin)
    assert r_del.status_code == 200

    # Act: GET /admin/users
    headers_get = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r = client_admin.get("/admin/users", headers=headers_get)

    # Assert: header exists and reflects at least one deletion; body shape unchanged
    assert r.status_code == 200
    assert "X-Users-Deleted-Total" in r.headers
    try:
        deleted_total = int(r.headers["X-Users-Deleted-Total"])
    except Exception:
        deleted_total = -1
    assert deleted_total >= 1

    body = r.get_json()
    assert isinstance(body, dict)
    assert "items" in body and "total" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)
