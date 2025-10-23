from __future__ import annotations

import json

from core.app_factory import create_app


def make_client(testing: bool = True):
    app = create_app({"TESTING": testing})
    return app.test_client()


def test_tasks_list_unauthenticated_returns_401_problem():
    c = make_client()
    # Provide tenant context to avoid unrelated 500 from missing tenant
    rv = c.get("/tasks/", headers={"X-Tenant-Id": "1"})
    assert rv.status_code == 401
    assert rv.mimetype == "application/problem+json"
    body = rv.get_json()
    assert body["status"] == 401
    assert body["type"].endswith("/errors/unauthorized")


def test_tasks_create_viewer_forbidden_has_required_role_editor():
    c = make_client()
    headers = {"X-Tenant-Id": "1", "X-User-Role": "viewer", "X-User-Id": "10"}
    rv = c.post("/tasks/", json={"title": "x"}, headers=headers)
    assert rv.status_code == 403
    assert rv.mimetype == "application/problem+json"
    body = rv.get_json()
    # RFC7807 core fields
    assert body["type"].endswith("/errors/forbidden")
    assert body["title"] == "Forbidden"
    assert body["detail"]
    assert body["status"] == 403
    # extension fields
    assert body.get("required_role") == "editor"
    assert body.get("invalid_params")
    assert body["invalid_params"][0]["name"] == "required_role"
    assert body["invalid_params"][0]["value"] == "editor"


def test_tasks_update_requires_editor_or_above():
    c = make_client()
    headers = {"X-Tenant-Id": "1", "X-User-Role": "viewer", "X-User-Id": "10"}
    # Require roles decorator should trigger before endpoint logic
    rv = c.put("/tasks/123", json={"title": "a"}, headers=headers)
    assert rv.status_code == 403
    body = rv.get_json()
    # RFC7807 + required_role
    assert body["status"] == 403
    assert body.get("required_role") == "editor"
    assert body.get("invalid_params")
    assert body["invalid_params"][0]["name"] == "required_role"
    assert body["invalid_params"][0]["value"] == "editor"
