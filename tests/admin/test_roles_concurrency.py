from __future__ import annotations

import hashlib

from core.db import get_session
from core.models import User


def _admin_headers(client_admin, csrf: str) -> dict[str, str]:
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = csrf
    return {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": csrf}


def _seed_user(tenant_id: int = 1, email: str = "r1@example.com", role: str = "viewer") -> int:
    db = get_session()
    try:
        u = User(tenant_id=tenant_id, email=email, password_hash="!", role=role)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _etag_for_user(user_id: int) -> str:
    db = get_session()
    try:
        row = db.query(User).filter_by(id=user_id).first()
        ts = getattr(row, "updated_at", None)
        ts_iso = ts.isoformat() if ts is not None else ""
        return 'W/"' + hashlib.sha1(f"{user_id}:{ts_iso}".encode()).hexdigest() + '"'
    finally:
        db.close()


def test_roles_get_200_and_304(client_admin):
    uid = _seed_user(email="rolesc1@example.com")
    base = {"X-User-Role": "admin", "X-Tenant-Id": "1"}

    r1 = client_admin.get(f"/admin/roles/{uid}", headers=base)
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag and etag.startswith('W/"')

    # 304 with If-None-Match
    r2 = client_admin.get(f"/admin/roles/{uid}", headers={**base, "If-None-Match": etag})
    assert r2.status_code == 304

    # 304 with wildcard
    r3 = client_admin.get(f"/admin/roles/{uid}", headers={**base, "If-None-Match": "*"})
    assert r3.status_code == 304


def test_roles_patch_if_match_required_and_changes_etag(client_admin):
    uid = _seed_user(email="rolesc2@example.com")
    headers = _admin_headers(client_admin, csrf="rc2")

    # Missing If-Match for change -> 412
    r_missing = client_admin.patch(f"/admin/roles/{uid}", json={"role": "editor"}, headers=headers)
    assert r_missing.status_code == 412

    # Wrong If-Match -> 412
    r_wrong = client_admin.patch(
        f"/admin/roles/{uid}", json={"role": "editor"}, headers={**headers, "If-Match": 'W/"deadbeef"'}
    )
    assert r_wrong.status_code == 412

    # Correct If-Match -> 200 + new ETag
    etag = _etag_for_user(uid)
    r_ok = client_admin.patch(
        f"/admin/roles/{uid}", json={"role": "editor"}, headers={**headers, "If-Match": etag}
    )
    assert r_ok.status_code == 200
    etag2 = r_ok.headers.get("ETag")
    assert etag2 and etag2 != etag

    # Idempotent: same role, no If-Match required -> 200
    r_idem = client_admin.patch(f"/admin/roles/{uid}", json={"role": "editor"}, headers=headers)
    assert r_idem.status_code == 200


def test_roles_delete_requires_if_match(client_admin):
    uid = _seed_user(email="rolesc3@example.com")
    headers = _admin_headers(client_admin, csrf="rc3")
    etag = _etag_for_user(uid)

    # Multi-ETag header where second matches
    multi = 'W/"deadbeef", ' + etag
    r = client_admin.delete(f"/admin/roles/{uid}", headers={**headers, "If-Match": multi})
    assert r.status_code == 204
