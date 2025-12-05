import json

from flask import Flask

from core.app_factory import create_app


def _make_app(overrides=None, defaults=None) -> Flask:
    cfg = {}
    if overrides is not None:
        cfg["FEATURE_LIMITS_JSON"] = json.dumps(overrides)
    if defaults is not None:
        cfg["FEATURE_LIMITS_DEFAULTS_JSON"] = json.dumps(defaults)
    cfg["TESTING"] = True
    return create_app(cfg)


def test_admin_limits_unauthorized():
    app = _make_app()
    c = app.test_client()
    # No auth headers -> 401 (handled by auth system before route logic)
    rv = c.get("/admin/limits")
    assert rv.status_code == 401
    body = rv.get_json()
    # Assert RFC7807 ProblemDetails shape
    assert isinstance(body, dict)
    assert body.get("title") == "Unauthorized"
    assert body.get("status") == 401
    # Central auth adapter returns custom message in detail
    assert body.get("detail") == "authentication required"


def test_admin_limits_forbidden_role():
    app = _make_app()
    c = app.test_client()
    # Provide viewer role (not admin) -> 403
    # Provide viewer role with tenant context -> 403 Forbidden
    rv = c.get("/admin/limits", headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"})
    assert rv.status_code == 403
    body = rv.get_json()
    assert isinstance(body, dict)
    assert body.get("title") == "Forbidden"
    assert body.get("status") == 403


def test_admin_limits_defaults_listing():
    app = _make_app(defaults={"notes_list": {"quota": 99, "per": 60}})
    c = app.test_client()
    rv = c.get("/admin/limits", headers={"X-User-Role": "admin"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["ok"] is True
    assert any(it["name"] == "notes_list" and it["source"] == "default" for it in data["items"])


def test_admin_limits_tenant_override_listing():
    overrides = {"tenant:1:notes_list": {"quota": 7, "per": 30}}
    defaults = {"notes_list": {"quota": 10, "per": 60}}
    app = _make_app(overrides=overrides, defaults=defaults)
    c = app.test_client()
    rv = c.get("/admin/limits?tenant_id=1", headers={"X-User-Role": "admin"})
    assert rv.status_code == 200
    data = rv.get_json()
    # Ensure override present with tenant source
    assert any(it["name"] == "notes_list" and it["source"] == "tenant" for it in data["items"])


def test_admin_limits_fallback_name_filter():
    app = _make_app()
    c = app.test_client()
    rv = c.get("/admin/limits?tenant_id=5&name=unknown_limit", headers={"X-User-Role": "admin"})
    assert rv.status_code == 200
    data = rv.get_json()
    # Name filter triggers fallback row
    assert len(data["items"]) == 1
    row = data["items"][0]
    assert row["name"] == "unknown_limit"
    assert row["source"] == "fallback"
    assert row["tenant_id"] == 5


def test_admin_limits_invalid_tenant_id():
    app = _make_app()
    c = app.test_client()
    rv = c.get("/admin/limits?tenant_id=abc", headers={"X-User-Role": "admin"})
    assert rv.status_code == 400
    data = rv.get_json()
    assert data["error"] == "bad_request"


def test_admin_limits_pagination():
    # Provide several defaults to test pagination slice stability
    defaults = {f"limit{i}": {"quota": 5 + i, "per": 60} for i in range(15)}
    app = _make_app(defaults=defaults)
    c = app.test_client()
    rv = c.get("/admin/limits?page=2&size=5", headers={"X-User-Role": "admin"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["meta"]["page"] == 2
    assert data["meta"]["size"] == 5
    assert data["meta"]["total"] == 15
    assert len(data["items"]) == 5
