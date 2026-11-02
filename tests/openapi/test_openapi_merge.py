import os

import pytest

from core.app_factory import create_app


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    db_file = tmp_path / "db.sqlite"
    builder_db_file = tmp_path / "builder.sqlite"
    database_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(builder_db_file))
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": database_url,
            "BUILDER_DB_PATH": str(builder_db_file),
        }
    )
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


def test_admin_paths_absent_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAPI_INCLUDE_PARTS", "0")
    db_file = tmp_path / "disabled.sqlite"
    builder_db_file = tmp_path / "disabled_builder.sqlite"
    database_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BUILDER_DB_PATH", str(builder_db_file))
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": database_url,
            "BUILDER_DB_PATH": str(builder_db_file),
        }
    )
    c = app.test_client()
    r = c.get("/openapi.json")
    spec = r.get_json()
    assert "/api/admin/stats" not in spec.get("paths", {}), "admin stats should be absent when merge disabled"
    schemas = spec.get("components", {}).get("schemas", {})
    assert "AdminStats" not in schemas, "AdminStats schema should be absent when merge disabled"
