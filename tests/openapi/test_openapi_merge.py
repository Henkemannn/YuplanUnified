import os

import pytest

from core.app_factory import create_app


@pytest.fixture()
def app_env(tmp_path):
    db_file = tmp_path / "db.sqlite"
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": f"sqlite:///{db_file}"})
    return app


def _client(app):
    return app.test_client()


def test_admin_paths_present_by_default(app_env):
    c = _client(app_env)
    r = c.get("/openapi.json")
    assert r.status_code == 200
    spec = r.get_json()
    assert "/api/admin/stats" in spec.get("paths", {}), "admin stats path missing by default"
    # At least one admin schema (AdminStats)
    schemas = spec.get("components", {}).get("schemas", {})
    assert "AdminStats" in schemas, "AdminStats schema missing after merge"


def test_admin_paths_absent_when_disabled(monkeypatch):
    monkeypatch.setenv("OPENAPI_INCLUDE_PARTS", "0")
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "database_url": "sqlite:///disabled.sqlite"})
    c = app.test_client()
    r = c.get("/openapi.json")
    spec = r.get_json()
    assert "/api/admin/stats" not in spec.get("paths", {}), "admin stats should be absent when merge disabled"
    schemas = spec.get("components", {}).get("schemas", {})
    assert "AdminStats" not in schemas, "AdminStats schema should be absent when merge disabled"
