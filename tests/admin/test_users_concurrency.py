from __future__ import annotations

from ._problem_utils import assert_problem


def _admin_headers(client_admin, csrf: str) -> dict[str, str]:
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = csrf
    return {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": csrf}


def _create_user(client_admin, email: str = "c1@example.com", role: str = "viewer") -> tuple[int, str]:
    headers = _admin_headers(client_admin, csrf="c1")
    r = client_admin.post("/admin/users", json={"email": email, "role": role}, headers=headers)
    assert r.status_code == 201
    body = r.get_json()
    assert isinstance(body, dict)
    uid = int(str(body["id"]))
    etag = r.headers.get("ETag")
    assert etag and etag.startswith('W/"')
    return uid, etag


def test_patch_if_match_required_and_mismatch_then_success(client_admin):
    uid, etag = _create_user(client_admin, email="cx1@example.com")
    headers = _admin_headers(client_admin, csrf="p1")

    # Missing If-Match -> 412 problem
    r_missing = client_admin.patch(f"/admin/users/{uid}", json={"role": "editor"}, headers=headers)
    b = assert_problem(r_missing, 412, "Precondition Failed")
    assert "expected_etag" in b and "got_etag" in b

    # Wrong If-Match -> 412 problem
    headers_wrong = dict(headers)
    headers_wrong["If-Match"] = 'W/"deadbeef"'
    r_wrong = client_admin.patch(f"/admin/users/{uid}", json={"role": "editor"}, headers=headers_wrong)
    b2 = assert_problem(r_wrong, 412, "Precondition Failed")
    assert b2.get("got_etag") == 'W/"deadbeef"'

    # Correct If-Match -> 200 and ETag present (and changes if updated_at changes)
    headers_ok = dict(headers)
    headers_ok["If-Match"] = etag
    r_ok = client_admin.patch(f"/admin/users/{uid}", json={"role": "editor"}, headers=headers_ok)
    assert r_ok.status_code == 200
    etag2 = r_ok.headers.get("ETag")
    assert etag2 and etag2.startswith('W/"') and etag2 != etag


def test_put_if_match_required_and_mismatch_then_success(client_admin):
    uid, etag = _create_user(client_admin, email="cx2@example.com")
    headers = _admin_headers(client_admin, csrf="p2")

    # Missing If-Match -> 412
    r_missing = client_admin.put(
        f"/admin/users/{uid}", json={"email": "x@ex.com", "role": "viewer"}, headers=headers
    )
    assert_problem(r_missing, 412, "Precondition Failed")

    # Wrong If-Match -> 412
    headers_wrong = dict(headers)
    headers_wrong["If-Match"] = 'W/"deadbeef"'
    r_wrong = client_admin.put(
        f"/admin/users/{uid}", json={"email": "x@ex.com", "role": "viewer"}, headers=headers_wrong
    )
    assert_problem(r_wrong, 412, "Precondition Failed")

    # Correct -> 200 and ETag present
    headers_ok = dict(headers)
    headers_ok["If-Match"] = etag
    r_ok = client_admin.put(
        f"/admin/users/{uid}", json={"email": "x@ex.com", "role": "editor"}, headers=headers_ok
    )
    assert r_ok.status_code == 200
    etag2 = r_ok.headers.get("ETag")
    assert etag2 and etag2.startswith('W/"') and etag2 != etag


def test_delete_requires_if_match_and_succeeds_with_correct(client_admin):
    uid, etag = _create_user(client_admin, email="cx3@example.com")
    headers = _admin_headers(client_admin, csrf="p3")

    # Missing If-Match -> 412
    r_missing = client_admin.delete(f"/admin/users/{uid}", headers=headers)
    assert_problem(r_missing, 412, "Precondition Failed")

    # Wrong -> 412
    headers_wrong = dict(headers)
    headers_wrong["If-Match"] = 'W/"deadbeef"'
    r_wrong = client_admin.delete(f"/admin/users/{uid}", headers=headers_wrong)
    assert_problem(r_wrong, 412, "Precondition Failed")

    # Correct -> 204
    headers_ok = dict(headers)
    headers_ok["If-Match"] = etag
    r_ok = client_admin.delete(f"/admin/users/{uid}", headers=headers_ok)
    assert r_ok.status_code == 204
    assert (r_ok.data is None) or (r_ok.data == b"")
