from __future__ import annotations

import hashlib

from core.db import get_session
from core.models import TenantFeatureFlag


def _admin_headers(client_admin, csrf: str) -> dict[str, str]:
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = csrf
    return {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": csrf}


def _seed_flag(key: str = "flagc1", enabled: bool = False, tenant_id: int = 1) -> None:
    db = get_session()
    try:
        row = db.query(TenantFeatureFlag).filter_by(tenant_id=tenant_id, name=key).first()
        if not row:
            row = TenantFeatureFlag(tenant_id=tenant_id, name=key, enabled=enabled)
            db.add(row)
            db.commit()
    finally:
        db.close()


def _etag_for_flag(key: str, tenant_id: int = 1) -> str:
    db = get_session()
    try:
        row = db.query(TenantFeatureFlag).filter_by(tenant_id=tenant_id, name=key).first()
        ts = getattr(row, "updated_at", None)
        ts_iso = ts.isoformat() if ts is not None else ""
        return 'W/"' + hashlib.sha1(f"{key}:{ts_iso}".encode()).hexdigest() + '"'
    finally:
        db.close()


def test_flags_get_200_and_304(client_admin):
    _seed_flag("flagc_g1")
    base = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r1 = client_admin.get("/admin/feature-flags/flagc_g1", headers=base)
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag and etag.startswith('W/"')

    r2 = client_admin.get("/admin/feature-flags/flagc_g1", headers={**base, "If-None-Match": etag})
    assert r2.status_code == 304

    r3 = client_admin.get("/admin/feature-flags/flagc_g1", headers={**base, "If-None-Match": "*"})
    assert r3.status_code == 304


def test_flags_patch_if_match_required_and_changes_etag(client_admin):
    _seed_flag("flagc_p1")
    headers = _admin_headers(client_admin, csrf="fc1")

    # Missing If-Match -> 412 on change
    r_missing = client_admin.patch("/admin/feature-flags/flagc_p1", json={"enabled": True}, headers=headers)
    assert r_missing.status_code == 412

    # Wrong If-Match -> 412
    r_wrong = client_admin.patch(
        "/admin/feature-flags/flagc_p1", json={"notes": "X"}, headers={**headers, "If-Match": 'W/"deadbeef"'}
    )
    assert r_wrong.status_code == 412

    # Correct If-Match -> 200 and ETag changes
    etag = _etag_for_flag("flagc_p1")
    r_ok = client_admin.patch(
        "/admin/feature-flags/flagc_p1", json={"enabled": True, "notes": "updated"}, headers={**headers, "If-Match": etag}
    )
    assert r_ok.status_code == 200
    etag2 = r_ok.headers.get("ETag")
    assert etag2 and etag2 != etag

    # Idempotent no-op allowed without If-Match
    r_idem = client_admin.patch(
        "/admin/feature-flags/flagc_p1", json={"enabled": True, "notes": "updated"}, headers=headers
    )
    assert r_idem.status_code == 200


def test_flags_delete_requires_if_match_and_multi_etag(client_admin):
    _seed_flag("flagc_d1")
    headers = _admin_headers(client_admin, csrf="fc2")
    etag = _etag_for_flag("flagc_d1")
    multi = 'W/"deadbeef", ' + etag
    r = client_admin.delete("/admin/feature-flags/flagc_d1", headers={**headers, "If-Match": multi})
    assert r.status_code == 204
