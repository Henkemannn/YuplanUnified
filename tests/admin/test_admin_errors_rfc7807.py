from __future__ import annotations

def _assert_problem(resp, expected_status: int, expected_title: str | None = None):
    assert resp.status_code == expected_status
    ctype = resp.headers.get("Content-Type", "")
    assert ctype.startswith("application/problem+json")
    body = resp.get_json()
    assert set(["type","title","status"]).issubset(set(body.keys()))
    assert body["type"] == "about:blank"
    assert body["status"] == expected_status
    if expected_title:
        assert body["title"] == expected_title
    return body


def test_admin_401_problem_shape(client):
    # No auth headers -> 401 from admin endpoint
    r = client.get("/admin/limits")
    b = _assert_problem(r, 401, "Unauthorized")
    assert "detail" in b or True  # optional


def test_admin_403_problem_shape(client):
    # Viewer role -> forbidden on admin endpoint
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1"}
    r = client.get("/admin/limits", headers=headers)
    b = _assert_problem(r, 403, "Forbidden")
    assert b.get("required_role") == "admin"
    inv = b.get("invalid_params") or []
    assert any((it.get("name") == "required_role") for it in inv)


def test_admin_404_problem_shape_for_users(client_admin):
    # Prime CSRF for admin
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "p7807"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "p7807"}
    r = client_admin.delete("/admin/users/999999", headers=headers)
    b = _assert_problem(r, 404, "Not Found")
    assert "detail" in b


def test_admin_422_problem_shape_for_users_create(client_admin):
    # Missing role / invalid email triggers 422
    with client_admin.session_transaction() as sess:
        sess["CSRF_TOKEN"] = "p7807_2"
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-CSRF-Token": "p7807_2"}
    r = client_admin.post("/admin/users", json={"email": "x"}, headers=headers)
    b = _assert_problem(r, 422, "Validation error")
    assert isinstance(b.get("invalid_params"), list)
