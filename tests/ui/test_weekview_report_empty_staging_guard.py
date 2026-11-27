from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

import core.db as db_module
from core.app_factory import create_app
from core.db import create_all, get_session
from core.weekview.schema import ensure_weekview_schema
from tests._auth_site_helpers import login_bound_user


@pytest.fixture
def isolated_legacy_client(tmp_path, monkeypatch, request):
    env_names = (
        "DATABASE_URL",
        "BUILDER_DB_PATH",
        "APP_ENV",
        "DEPLOY_ENV",
        "FLASK_ENV",
        "YP_ENABLE_SQLITE_BOOTSTRAP",
        "YUPLAN_ALLOW_SCHEMA_REPAIR",
        "YUPLAN_ALLOW_DESTRUCTIVE_DB",
        "ALLOW_DESTRUCTIVE_DB",
    )
    previous_env = {name: os.environ.get(name) for name in env_names}
    database_path = tmp_path / "main.db"
    builder_path = tmp_path / "builder.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("BUILDER_DB_PATH", str(builder_path))
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("YP_ENABLE_SQLITE_BOOTSTRAP", raising=False)

    def cleanup():
        if db_module._SessionFactory is not None:
            db_module._SessionFactory.remove()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._SessionFactory = None
        db_module._engine = None
        for name, value in previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    request.addfinalizer(cleanup)
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": f"sqlite:///{database_path.as_posix()}",
            "BUILDER_DB_PATH": str(builder_path),
        }
    )
    with app.app_context():
        create_all()
        db = get_session()
        try:
            ensure_weekview_schema(db.connection())
            db.commit()
        finally:
            db.close()
    return app.test_client()


def _h(role: str) -> dict:
    return {"X-User-Role": role, "X-Tenant-Id": "1", "X-User-Id": "1"}


def _seed_site_and_department(app, site_id: str, dep_id: str) -> None:
    with app.app_context():
        create_all()
        db = get_session()
        try:
            ensure_weekview_schema(db.connection())
            db.commit()
            db.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id, version) VALUES(:i,:n,1,0) "
                    "ON CONFLICT(id) DO NOTHING"
                ),
                {"i": site_id, "n": "Guard Site"},
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed, version) "
                    "VALUES(:i,:s,:n,'fixed',0,0) ON CONFLICT(id) DO NOTHING"
                ),
                {"i": dep_id, "s": site_id, "n": "Guard Dep"},
            )
            db.commit()
        finally:
            db.close()


def _force_legacy_alt2_schema(app) -> None:
    with app.app_context():
        db = get_session()
        try:
            db.execute(text("DROP TABLE IF EXISTS weekview_alt2_flags"))
            db.execute(
                text(
                    """
                    CREATE TABLE weekview_alt2_flags (
                      tenant_id TEXT NOT NULL,
                      department_id TEXT NOT NULL,
                      year INTEGER NOT NULL,
                      week INTEGER NOT NULL,
                      day_of_week INTEGER NOT NULL,
                      is_alt2 INTEGER NOT NULL DEFAULT 0,
                      UNIQUE (tenant_id, department_id, year, week, day_of_week)
                    )
                    """
                )
            )
            db.commit()
        finally:
            db.close()


def _weekview_schema_and_counts(app) -> tuple[dict[str, tuple[str, ...]], dict[str, int]]:
    with app.app_context():
        db = get_session()
        try:
            tables = (
                "weekview_registrations",
                "weekview_versions",
                "weekview_residents_count",
                "weekview_alt2_flags",
            )
            schemas = {}
            counts = {}
            for table in tables:
                rows = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
                schemas[table] = tuple(str(row[1]) for row in rows)
                counts[table] = int(
                    db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                )
            return schemas, counts
        finally:
            db.close()


def test_weekview_ui_legacy_alt2_schema_does_not_500(isolated_legacy_client):
    app = isolated_legacy_client.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    _seed_site_and_department(app, site_id, dep_id)
    _force_legacy_alt2_schema(app)
    login_bound_user(isolated_legacy_client, site_id=site_id)
    before_schema, before_counts = _weekview_schema_and_counts(app)

    resp = isolated_legacy_client.get(
        f"/ui/weekview?site_id={site_id}&department_id={dep_id}&year=2026&week=11",
    )
    body = resp.get_data(as_text=True).lower()
    assert resp.status_code == 500
    assert all(
        secret not in body
        for secret in ("traceback", "weekviewschemaerror", "sqlalchemy", "select ", "drop table")
    )
    assert _weekview_schema_and_counts(app) == (before_schema, before_counts)


def test_weekview_report_ui_legacy_alt2_schema_empty_dataset_fails_closed(
    isolated_legacy_client,
):
    app = isolated_legacy_client.application
    site_id = str(uuid.uuid4())
    dep_id = str(uuid.uuid4())
    _seed_site_and_department(app, site_id, dep_id)
    _force_legacy_alt2_schema(app)
    login_bound_user(isolated_legacy_client, site_id=site_id)
    before_schema, before_counts = _weekview_schema_and_counts(app)

    resp = isolated_legacy_client.get(
        f"/ui/reports/weekview?site_id={site_id}&year=2026&week=11",
    )
    body = resp.get_data(as_text=True).lower()
    assert resp.status_code == 500
    assert all(
        secret not in body
        for secret in ("traceback", "weekviewschemaerror", "sqlalchemy", "select ", "drop table")
    )
    assert _weekview_schema_and_counts(app) == (before_schema, before_counts)


def test_weekview_report_ui_canonical_schema_empty_dataset_does_not_500(client_admin):
    app = client_admin.application
    site_id = str(uuid.uuid4())
    _seed_site_and_department(app, site_id, str(uuid.uuid4()))
    login_bound_user(client_admin, site_id=site_id)

    resp = client_admin.get(
        f"/ui/reports/weekview?site_id={site_id}&year=2026&week=11",
    )
    assert resp.status_code == 200


def test_reports_weekly_no_site_selected_redirects_not_500(client_admin):
    site_id = "weekly-no-site"
    _seed_site_and_department(client_admin.application, site_id, str(uuid.uuid4()))
    login_bound_user(client_admin, site_id=site_id, role="superuser")
    with client_admin.session_transaction() as sess:
        sess.pop("site_id", None)

    resp = client_admin.get(
        "/ui/reports/weekly?year=2026&week=11",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 400, 403)
