from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

import core.db as db_module
import core.weekview.repo as repo_module
from core.app_factory import create_app
from core.db import get_session
from core.models import Base
from core.weekview.repo import WeekviewRepo
from core.weekview.schema import WeekviewSchemaError, ensure_weekview_schema


@pytest.fixture
def isolated_weekview_app(tmp_path, monkeypatch, request):
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
        db = get_session()
        try:
            ensure_weekview_schema(db.connection())
            for name in (
                "department_residents_schedule", "department_residents_weekly",
                "department_diet_defaults", "department_diet_overrides", "dietary_types",
            ):
                Base.metadata.tables[name].create(db.connection(), checkfirst=True)
            db.execute(
                text(
                    """
                    CREATE TABLE sites (
                        id TEXT PRIMARY KEY,
                        tenant_id INTEGER NOT NULL
                    )
                    """
                )
            )
            db.execute(
                text(
                    """
                    CREATE TABLE departments (
                        id TEXT PRIMARY KEY,
                        site_id TEXT NOT NULL,
                        resident_count_fixed INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            db.execute(
                text(
                    "INSERT INTO sites(id, tenant_id) VALUES ('site-1', 1)"
                )
            )
            db.execute(
                text(
                    "INSERT INTO departments(id, site_id) VALUES ('dep-1', 'site-1')"
                )
            )
            db.execute(
                text(
                    """
                    CREATE TABLE tenant_feature_flags (
                        tenant_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        enabled INTEGER NOT NULL,
                        PRIMARY KEY (tenant_id, name)
                    )
                    """
                )
            )
            db.execute(
                text(
                    "INSERT INTO tenant_feature_flags(tenant_id, name, enabled) "
                    "VALUES (1, 'ff.weekview.enabled', 1)"
                )
            )
            db.execute(
                text(
                    """
                    CREATE TABLE department_menu_choices (
                        id INTEGER PRIMARY KEY,
                        tenant_id INTEGER NOT NULL,
                        site_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        weekday INTEGER NOT NULL,
                        meal TEXT NOT NULL,
                        selected_variant TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            )
            db.execute(
                text(
                    """
                    INSERT INTO weekview_registrations(
                        tenant_id, department_id, year, week, day_of_week,
                        meal, diet_type, marked
                    ) VALUES (1, 'dep-1', 2026, 6, 1, 'lunch', 'Gluten', 1)
                    """
                )
            )
            db.commit()
        finally:
            db.close()

    yield app


def _capture_sql(engine):
    statements: list[str] = []
    connection_ids: list[int] = []

    def capture(connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
        connection_ids.append(id(connection.connection.driver_connection))

    event.listen(engine, "before_cursor_execute", capture)
    return statements, connection_ids, capture


@pytest.mark.parametrize("name,predicate", [
    ("ux_residents_schedule_forever", "week IS NULL OR 1=1"),
    ("ux_residents_schedule_week", "week IS NOT NULL AND weekday = 1"),
])
def test_resident_readiness_rejects_different_partial_index_predicate(isolated_weekview_app, name, predicate):
    from core.weekview.service import WeekviewService

    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            db.execute(text(f"DROP INDEX {name}"))
            keys = ("department_id, weekday, meal" if name.endswith("forever")
                    else "department_id, week, weekday, meal")
            db.execute(text(f"CREATE UNIQUE INDEX {name} ON department_residents_schedule ({keys}) WHERE {predicate}"))
            db.commit()
        finally:
            db.close()
        with pytest.raises(WeekviewSchemaError, match="Residents schema incompatible"):
            WeekviewService()._verify_residents_schema()


def test_readiness_uses_session_connection_and_preserves_transaction(
    isolated_weekview_app,
):
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO weekview_versions("
                    "tenant_id, department_id, year, week, version"
                    ") VALUES (1, 'dep-1', 2026, 6, 4)"
                )
            )
            session_connection_id = id(db.connection().connection.driver_connection)
            engine = db.bind
            statements, connection_ids, listener = _capture_sql(engine)
            try:
                WeekviewRepo()._verify_schema_in_session(db)
                assert db.in_transaction()
                assert connection_ids
                assert all(connection_id == session_connection_id for connection_id in connection_ids)
                db.rollback()
            finally:
                event.remove(engine, "before_cursor_execute", listener)
        finally:
            db.close()

    assert not any(
        statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "COMMIT", "ROLLBACK"))
        for statement in statements
    )
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM weekview_versions "
                    "WHERE tenant_id=1 AND department_id='dep-1' AND year=2026 AND week=6"
                )
            ).scalar_one() == 0
        finally:
            db.close()


def test_schema_scope_cannot_be_reused_for_another_engine(isolated_weekview_app, tmp_path, monkeypatch):
    with isolated_weekview_app.app_context():
        engine_b = create_engine(f"sqlite:///{(tmp_path / 'other.db').as_posix()}")
        session_b = Session(engine_b)
        try:
            repo = WeekviewRepo()
            with repo.schema_verified():
                monkeypatch.setattr(repo_module, "get_session", lambda: session_b)
                with pytest.raises(WeekviewSchemaError, match="required table missing"):
                    with repo.schema_verified():
                        pass
        finally:
            session_b.close()
            engine_b.dispose()


def test_service_operation_verifies_schema_once_per_operation(isolated_weekview_app, monkeypatch):
    from core.weekview.service import WeekviewService

    calls = []
    verify = repo_module.verify_weekview_schema

    def count_verification(connection):
        calls.append(connection)
        return verify(connection)

    monkeypatch.setattr(repo_module, "verify_weekview_schema", count_verification)
    with isolated_weekview_app.app_context():
        WeekviewService().fetch_weekview_conditional(1, 2026, 6, "dep-1", None, "site-1")
    assert len(calls) == 1


def test_canonical_weekview_read_executes_no_runtime_ddl(isolated_weekview_app):
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            engine = db.bind
            statements, _connection_ids, listener = _capture_sql(engine)
            try:
                payload = WeekviewRepo().get_weekview(1, 2026, 6, "dep-1", "site-1")
            finally:
                event.remove(engine, "before_cursor_execute", listener)
        finally:
            db.close()

    assert payload["department_summaries"][0]["marks"] == [
        {"day_of_week": 1, "meal": "lunch", "diet_type": "Gluten", "marked": True}
    ]
    ddl = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))
    ]
    assert not ddl, ddl


def test_weekview_mutations_execute_only_business_dml(isolated_weekview_app):
    from core.admin_repo import DietTypesRepo

    with isolated_weekview_app.app_context():
        diet_type_id = DietTypesRepo().create(
            site_id="site-1",
            name="Gluten",
            semantics="atomic",
        )
        db = get_session()
        try:
            engine = db.bind
            statements, _connection_ids, listener = _capture_sql(engine)
            try:
                repo = WeekviewRepo()
                repo.apply_operations(
                    1,
                    2026,
                    6,
                    "dep-1",
                    [{"day_of_week": 2, "meal": "lunch", "diet_type": str(diet_type_id), "marked": True}],
                )
                repo.set_residents_counts(
                    1,
                    2026,
                    6,
                    "dep-1",
                    [{"day_of_week": 2, "meal": "lunch", "count": 12}],
                )
                repo.set_alt2_flags(1, 2026, 6, "dep-1", [2], "site-1")
            finally:
                event.remove(engine, "before_cursor_execute", listener)
        finally:
            db.close()

    ddl = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))
    ]
    assert not ddl, ddl


@pytest.mark.parametrize("flag", ("YUPLAN_ALLOW_SCHEMA_REPAIR", "YUPLAN_ALLOW_DESTRUCTIVE_DB", "ALLOW_DESTRUCTIVE_DB"))
def test_missing_weekview_schema_fails_closed_without_runtime_repair(
    isolated_weekview_app, monkeypatch, flag
):
    monkeypatch.setenv(flag, "1")
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            engine = db.bind
            db.execute(text("DROP TABLE weekview_alt2_flags"))
            db.commit()
            statements, _connection_ids, listener = _capture_sql(engine)
            try:
                with pytest.raises(RuntimeError, match="schema incomplete"):
                    WeekviewRepo().get_weekview(1, 2026, 6, "dep-1", "site-1")
            finally:
                event.remove(engine, "before_cursor_execute", listener)
            assert db.execute(
                text(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type='table' AND name='weekview_alt2_flags'"
                )
            ).scalar_one() == 0
        finally:
            db.close()

    assert not any(
        statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))
        for statement in statements
    )


def test_legacy_alt2_schema_fails_without_repair_or_temp_table(isolated_weekview_app, monkeypatch):
    monkeypatch.setenv("YUPLAN_ALLOW_SCHEMA_REPAIR", "1")
    monkeypatch.setenv("YUPLAN_ALLOW_DESTRUCTIVE_DB", "1")
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_DB", "1")
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            engine = db.bind
            db.execute(text("DROP TABLE weekview_alt2_flags"))
            db.execute(
                text(
                    """
                    CREATE TABLE weekview_alt2_flags (
                        tenant_id INTEGER NOT NULL,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        day_of_week INTEGER NOT NULL,
                        is_alt2 INTEGER NOT NULL
                    )
                    """
                )
            )
            db.execute(
                text(
                    "INSERT INTO weekview_alt2_flags VALUES "
                    "(1, 'legacy-department', 2026, 6, 1, 1)"
                )
            )
            db.commit()
            statements, _connection_ids, listener = _capture_sql(engine)
            try:
                with pytest.raises(RuntimeError, match="schema incompatible"):
                    WeekviewRepo().get_version(1, 2026, 6, "legacy-department")
            finally:
                event.remove(engine, "before_cursor_execute", listener)
            row = db.execute(
                text("SELECT tenant_id, department_id, is_alt2 FROM weekview_alt2_flags")
            ).one()
            temp_count = db.execute(
                text(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type='table' AND name='weekview_alt2_flags_new'"
                )
            ).scalar_one()
        finally:
            db.close()

    assert tuple(row) == (1, "legacy-department", 1)
    assert temp_count == 0
    assert not any(
        statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))
        for statement in statements
    )


def test_schema_error_is_sanitized_in_actual_flask_request(isolated_weekview_app):
    feature_registry = isolated_weekview_app.feature_registry
    feature_registry.add("ff.weekview.enabled")
    feature_registry.set("ff.weekview.enabled", True)
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            db.execute(text("DROP TABLE weekview_alt2_flags"))
            db.commit()
        finally:
            db.close()

    client = isolated_weekview_app.test_client()
    with client.session_transaction() as session:
        session["site_id"] = "site-1"
    response = client.get(
        "/api/weekview?year=2026&week=6",
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    body = response.get_data(as_text=True).lower()
    assert response.status_code == 500
    assert "sqlite" not in body
    assert "traceback" not in body
    assert "weekview schema" not in body


def test_authenticated_get_with_department_and_conditional_schema_error(
    isolated_weekview_app,
):
    department_id = "11111111-1111-4111-8111-111111111111"
    feature_registry = isolated_weekview_app.feature_registry
    feature_registry.add("ff.weekview.enabled")
    feature_registry.set("ff.weekview.enabled", True)
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            db.execute(
                text("INSERT INTO departments(id, site_id) VALUES (:id, 'site-1')"),
                {"id": department_id},
            )
            db.execute(
                text(
                    """
                    INSERT INTO weekview_registrations(
                        tenant_id, department_id, year, week, day_of_week,
                        meal, diet_type, marked
                    ) VALUES (1, :department_id, 2026, 6, 1, 'lunch', 'Gluten', 1)
                    """
                ),
                {"department_id": department_id},
            )
            db.commit()
        finally:
            db.close()

    client = isolated_weekview_app.test_client()
    with client.session_transaction() as session:
        session["site_id"] = "site-1"
    headers = {"X-User-Role": "viewer", "X-Tenant-Id": "1"}
    response = client.get(
        f"/api/weekview?year=2026&week=6&department_id={department_id}",
        headers=headers,
    )
    assert response.status_code == 200
    etag = response.headers["ETag"]

    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            db.execute(text("DROP TABLE weekview_alt2_flags"))
            db.commit()
        finally:
            db.close()

    conditional = client.get(
        f"/api/weekview?year=2026&week=6&department_id={department_id}",
        headers={**headers, "If-None-Match": etag},
    )
    body = conditional.get_data(as_text=True).lower()
    assert conditional.status_code == 500
    assert conditional.status_code != 304
    assert "sqlite" not in body
    assert "traceback" not in body


def test_ui_request_does_not_render_empty_etag_on_schema_error(isolated_weekview_app):
    feature_registry = isolated_weekview_app.feature_registry
    feature_registry.add("ff.weekview.enabled")
    feature_registry.set("ff.weekview.enabled", True)
    with isolated_weekview_app.app_context():
        db = get_session()
        try:
            db.execute(text("DROP TABLE weekview_alt2_flags"))
            db.commit()
        finally:
            db.close()

    response = isolated_weekview_app.test_client().get(
        "/ui/weekview?site_id=site-1&department_id=dep-1&year=2026&week=6",
        headers={"X-User-Role": "viewer", "X-Tenant-Id": "1"},
    )
    body = response.get_data(as_text=True).lower()
    assert response.status_code >= 400
    assert "traceback" not in body
    assert "sqlite" not in body
