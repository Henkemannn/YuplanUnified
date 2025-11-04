from __future__ import annotations

from core.db import get_session
from core.models import TenantFeatureFlag, User


def _admin_headers(client_admin, csrf: str = "h1") -> dict[str, str]:
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = csrf
    return {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": csrf}


def _seed_user() -> int:
    db = get_session()
    try:
        u = db.query(User).filter_by(tenant_id=1, email="hdr1@example.com").first()
        if not u:
            u = User(tenant_id=1, email="hdr1@example.com", password_hash="!", role="viewer")
            db.add(u)
            db.commit()
            db.refresh(u)
        return int(u.id)
    finally:
        db.close()


def _seed_flag() -> None:
    db = get_session()
    try:
        if not db.query(TenantFeatureFlag).filter_by(tenant_id=1, name="hdr-flag").first():
            db.add(TenantFeatureFlag(tenant_id=1, name="hdr-flag", enabled=False, notes=""))
            db.commit()
    finally:
        db.close()


def test_if_none_match_invalid_returns_400_problem(client_admin):
    uid = _seed_user()
    base = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    # Invalid: unquoted token
    r1 = client_admin.get(f"/admin/users/{uid}", headers={**base, "If-None-Match": "deadbeef"})
    assert r1.status_code == 400
    b1 = r1.get_json()
    assert b1.get("title") == "Bad Request"
    inv = b1.get("invalid_params") or []
    assert any(p.get("name") == "If-None-Match" and p.get("reason") == "invalid_header" for p in inv)

    # Invalid: empty entity-tag ""
    r2 = client_admin.get(f"/admin/users/{uid}", headers={**base, "If-None-Match": '""'})
    assert r2.status_code == 400


def test_if_match_invalid_returns_400_problem(client_admin):
    uid = _seed_user()
    headers = _admin_headers(client_admin, csrf="hv1")
    # Invalid If-Match when a change would occur -> 400
    r = client_admin.patch(f"/admin/roles/{uid}", json={"role": "editor"}, headers={**headers, "If-Match": "abc"})
    assert r.status_code == 400
    b = r.get_json()
    inv = b.get("invalid_params") or []
    assert any(p.get("name") == "If-Match" and p.get("reason") == "invalid_header" for p in inv)


def test_flags_notes_none_vs_empty_noop(client_admin):
    _seed_flag()
    base = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    # Round-trip to get ETag
    r0 = client_admin.get("/admin/feature-flags/hdr-flag", headers=base)
    assert r0.status_code == 200
    r0.headers.get("ETag")
    # Change notes to empty string and enabled same -> no-op allowed without If-Match
    headers = _admin_headers(client_admin, csrf="hf1")
    r_noop = client_admin.patch(
        "/admin/feature-flags/hdr-flag",
        json={"enabled": False, "notes": ""},
        headers=headers,
    )
    assert r_noop.status_code == 200
    # Change notes to None (no-op) allowed without If-Match
    r_noop2 = client_admin.patch(
        "/admin/feature-flags/hdr-flag",
        json={"notes": None},
        headers=headers,
    )
    assert r_noop2.status_code == 200
