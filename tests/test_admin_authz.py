from __future__ import annotations

from core.app_factory import create_app


def _client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_admin_list_requires_admin():
    c = _client()
    # Simulate viewer session via headers (app_factory reads these in TESTING)
    headers = {"X-Tenant-Id": "1", "X-User-Role": "viewer", "X-User-Id": "10"}
    resp = c.get("/admin/units", headers=headers)
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["status"] == 403
    assert body["type"].endswith("/errors/forbidden")
    assert body["invalid_params"][0]["name"] == "required_role"
    assert body["invalid_params"][0]["value"] == "admin"


def test_admin_create_unauth():
    c = _client()
    # No auth/session headers
    resp = c.post("/admin/units", json={"name": "X"})
    assert resp.status_code == 401
    body = resp.get_json()
    assert body["type"].endswith("/errors/unauthorized")
