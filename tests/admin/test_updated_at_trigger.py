from __future__ import annotations

from datetime import datetime

from core.concurrency import user_etag


def _admin_headers(client_admin, csrf: str) -> dict[str, str]:
    # Ensure CSRF is in session for admin mutations
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = csrf
    return {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": csrf}


def _create_user(client_admin, email: str = "t1@example.com", role: str = "viewer") -> tuple[int, str]:
    headers = _admin_headers(client_admin, csrf="t0")
    r = client_admin.post("/admin/users", json={"email": email, "role": role}, headers=headers)
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert isinstance(body, dict)
    uid = int(str(body["id"]))
    etag = r.headers.get("ETag")
    assert etag and etag.startswith('W/"')
    return uid, etag


def test_updated_at_bumps_on_change_and_not_on_noop(client_admin):
    uid, etag1 = _create_user(client_admin, email="trig1@example.com", role="viewer")

    # Baseline GET
    r0 = client_admin.get(f"/admin/users/{uid}")
    assert r0.status_code == 200
    body0 = r0.get_json()
    ua0 = body0.get("updated_at")
    assert isinstance(ua0, str) or ua0 is None
    etag0 = r0.headers.get("ETag")
    assert etag0 and etag0.startswith('W/"')

    # Change (role)
    headers1 = _admin_headers(client_admin, csrf="t1")
    headers1["If-Match"] = etag0
    r1 = client_admin.patch(f"/admin/users/{uid}", json={"role": "editor"}, headers=headers1)
    assert r1.status_code == 200
    body1 = r1.get_json()
    ua1 = body1.get("updated_at")
    assert isinstance(ua1, str) or ua1 is None
    etag2 = r1.headers.get("ETag")
    assert etag2 and etag2 != etag0

    # Confirm updated_at increased when both present
    if isinstance(ua0, str) and isinstance(ua1, str):
        dt0 = datetime.fromisoformat(ua0)
        dt1 = datetime.fromisoformat(ua1)
        assert dt1 >= dt0

    # No-op PATCH (same role) should not require If-Match and should keep ETag/updated_at stable
    headers2 = _admin_headers(client_admin, csrf="t2")
    r2 = client_admin.patch(f"/admin/users/{uid}", json={"role": "editor"}, headers=headers2)
    assert r2.status_code == 200
    body2 = r2.get_json()
    ua2 = body2.get("updated_at")
    etag3 = r2.headers.get("ETag")
    assert etag3 == etag2
    assert ua2 == ua1


def test_etag_roundtrip_stability(client_admin):
    uid, _etag = _create_user(client_admin, email="trig2@example.com", role="viewer")

    # GET representation
    r = client_admin.get(f"/admin/users/{uid}")
    assert r.status_code == 200
    body = r.get_json()
    etag_header = r.headers.get("ETag")
    assert etag_header and etag_header.startswith('W/"')

    # Recompute ETag using id + parsed updated_at
    ua = body.get("updated_at")
    # If updated_at is None, weak tag should still be stable in our user_etag (based on empty string)
    if ua is None:
        recomputed = user_etag(uid, None)
    else:
        dt = datetime.fromisoformat(ua)
        recomputed = user_etag(uid, dt)

    # Normalize both (strip weak prefix and quotes) and compare
    def _norm(tag: str) -> str:
        t = tag
        if t.lower().startswith('w/"'):
            t = t[2:].lstrip()
        if t.startswith('"') and t.endswith('"'):
            t = t[1:-1]
        return t

    assert _norm(recomputed) == _norm(etag_header)
