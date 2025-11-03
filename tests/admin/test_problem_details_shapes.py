from __future__ import annotations

from ._problem_utils import assert_problem


def _admin_headers(client) -> dict[str, str]:
    # Prime CSRF for admin session
    with client.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "p_pd"
    return {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "p_pd"}


def test_412_problem_details_shape_and_etag_fields(client_admin):
    headers = _admin_headers(client_admin)

    # Create user
    r_create = client_admin.post("/admin/users", json={"email": "pd@ex", "role": "viewer"}, headers=headers)
    assert r_create.status_code == 201
    uid = r_create.get_json()["id"]
    etag1 = r_create.headers.get("ETag")
    assert isinstance(etag1, str) and etag1

    # First change (valid If-Match) to bump ETag
    r1 = client_admin.patch(f"/admin/users/{uid}", json={"role": "editor"}, headers={**headers, "If-Match": etag1})
    assert r1.status_code == 200
    etag2 = r1.headers.get("ETag")
    assert isinstance(etag2, str) and etag2 and etag2 != etag1

    # Second change with stale If-Match -> 412
    r2 = client_admin.patch(
        f"/admin/users/{uid}", json={"email": "pd2@ex"}, headers={**headers, "If-Match": etag1}
    )
    body = assert_problem(r2, 412, "Precondition Failed")
    # Required base keys
    for k in ("type", "title", "status", "detail"):
        assert k in body
    # ETag diagnostics present
    assert body.get("expected_etag") == etag2
    assert body.get("got_etag") == etag1


def test_400_invalid_header_problem_details_shape(client_admin):
    headers = _admin_headers(client_admin)

    # Create user
    r_create = client_admin.post("/admin/users", json={"email": "pd3@ex", "role": "viewer"}, headers=headers)
    assert r_create.status_code == 201
    uid = r_create.get_json()["id"]

    # Invalid If-Match header -> 400 Bad Request (problem+json)
    # Must attempt a real change so PATCH enforces If-Match parsing
    r = client_admin.patch(f"/admin/users/{uid}", json={"role": "editor"}, headers={**headers, "If-Match": "invalid"})
    body = assert_problem(r, 400, "Bad Request")
    # Required base keys
    for k in ("type", "title", "status", "detail"):
        assert k in body
    # No ETag diagnostics on 400
    assert "expected_etag" not in body and "got_etag" not in body


essential_admin_headers = {"X-User-Role": "admin", "X-Tenant-Id": "1"}


def test_304_if_none_match_empty_body(client_admin):
    headers = _admin_headers(client_admin)

    # Create and fetch user to get ETag
    r_create = client_admin.post("/admin/users", json={"email": "pd4@ex", "role": "viewer"}, headers=headers)
    assert r_create.status_code == 201
    uid = r_create.get_json()["id"]

    # GET user, capture ETag
    r_get = client_admin.get(f"/admin/users/{uid}", headers=essential_admin_headers)
    assert r_get.status_code == 200
    etag = r_get.headers.get("ETag")
    assert isinstance(etag, str) and etag

    # Conditional GET with If-None-Match -> 304, empty body
    r_cond = client_admin.get(f"/admin/users/{uid}", headers={**essential_admin_headers, "If-None-Match": etag})
    assert r_cond.status_code == 304
    assert r_cond.data == b""
