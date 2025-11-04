from __future__ import annotations

from uuid import uuid4


def _admin_headers(client_admin, csrf: str) -> dict[str, str]:
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = csrf
    return {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": csrf}


def _create_user(client_admin, email: str = "", role: str = "viewer") -> tuple[int, str]:
    if not email:
        email = f"{uuid4().hex[:8]}@ex.com"
    headers = _admin_headers(client_admin, csrf="g1")
    r = client_admin.post("/admin/users", json={"email": email, "role": role}, headers=headers)
    assert r.status_code == 201
    body = r.get_json()
    uid = int(str(body["id"]))
    etag = r.headers.get("ETag")
    assert etag and etag.startswith('W/"')
    return uid, etag


def test_get_returns_etag_and_200(client_admin):
    uid, _ = _create_user(client_admin)
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    r = client_admin.get(f"/admin/users/{uid}", headers=headers)
    assert r.status_code == 200
    assert r.headers.get("ETag", "").startswith('W/"')
    body = r.get_json()
    assert set(body.keys()) >= {"id", "email", "role", "updated_at"}


def test_get_if_none_match_returns_304(client_admin):
    uid, _ = _create_user(client_admin)
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}
    # First GET to obtain current ETag
    r1 = client_admin.get(f"/admin/users/{uid}", headers=headers)
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert etag and etag.startswith('W/"')

    # If-None-Match with same etag -> 304, empty body
    headers2 = dict(headers)
    headers2["If-None-Match"] = etag
    r2 = client_admin.get(f"/admin/users/{uid}", headers=headers2)
    assert r2.status_code == 304
    assert (r2.data is None) or (r2.data == b"")

    # If-None-Match with '*' -> 304 as resource exists
    headers3 = dict(headers)
    headers3["If-None-Match"] = "*"
    r3 = client_admin.get(f"/admin/users/{uid}", headers=headers3)
    assert r3.status_code == 304
