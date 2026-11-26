from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from core.app_factory import create_app
from core.db import create_all, get_session


def test_sqlite_testing_bootstrap_creates_alt2_compatibility_tables(tmp_path, monkeypatch):
    db_file = tmp_path / "bootstrap.db"
    database_url = f"sqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("YP_ENABLE_SQLITE_BOOTSTRAP", "1")

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "database_url": database_url,
            "FORCE_DB_REINIT": True,
        }
    )

    with app.app_context():
        create_all()
        session = get_session()
        try:
            engine = session.get_bind()
            inspector = inspect(engine)

            tables = set(inspector.get_table_names())
            assert "department_menu_choices" in tables
            assert "alt2_flags" in tables
            assert "weekview_alt2_flags" in tables

            alt2_columns = [column["name"] for column in inspector.get_columns("alt2_flags")]
            assert alt2_columns == [
                "site_id",
                "department_id",
                "week",
                "weekday",
                "enabled",
                "version",
                "updated_at",
            ]
            assert inspector.get_pk_constraint("alt2_flags")["constrained_columns"] == [
                "site_id",
                "department_id",
                "week",
                "weekday",
            ]

            weekview_columns = [column["name"] for column in inspector.get_columns("weekview_alt2_flags")]
            assert weekview_columns == [
                "site_id",
                "department_id",
                "year",
                "week",
                "day_of_week",
                "enabled",
                "updated_at",
            ]
            unique_constraints = inspector.get_unique_constraints("weekview_alt2_flags")
            assert any(
                constraint.get("column_names") == [
                    "site_id",
                    "department_id",
                    "year",
                    "week",
                    "day_of_week",
                ]
                for constraint in unique_constraints
            )
        finally:
            session.close()


@pytest.mark.parametrize("error", (RuntimeError("schema failure"), SQLAlchemyError("database failure")))
def test_weekview_bootstrap_errors_propagate(tmp_path, monkeypatch, error):
    db_file = tmp_path / "bootstrap-errors.db"
    database_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("YP_ENABLE_SQLITE_BOOTSTRAP", "1")

    import core.weekview.schema as weekview_schema

    def fail(_connection):
        raise error

    monkeypatch.setattr(weekview_schema, "ensure_weekview_schema", fail)
    app = create_app(
        {
            "TESTING": False,
            "APP_ENV": "testing",
            "SECRET_KEY": "test",
            "database_url": database_url,
            "FORCE_DB_REINIT": True,
        }
    )

    with app.app_context(), pytest.raises(type(error), match=str(error)):
        create_all()


def test_weekview_bootstrap_flag_is_inactive_in_production(tmp_path, monkeypatch):
    db_file = tmp_path / "bootstrap-production.db"
    database_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("YP_ENABLE_SQLITE_BOOTSTRAP", "1")
    monkeypatch.setenv("SECRET_KEY", "production-test-secret-" + "x" * 40)
    monkeypatch.setenv("JWT_SECRET", "jwt-production-test-secret-" + "x" * 40)

    import core.weekview.schema as weekview_schema

    called = False

    def fail(_connection):
        nonlocal called
        called = True
        raise AssertionError("Weekview bootstrap must not run in production")

    monkeypatch.setattr(weekview_schema, "ensure_weekview_schema", fail)
    app = create_app(
        {
            "TESTING": False,
            "APP_ENV": "production",
            "SECRET_KEY": "test",
            "database_url": database_url,
            "FORCE_DB_REINIT": True,
        }
    )

    with app.app_context():
        create_all()
    assert called is False


def test_weekview_bootstrap_rejects_conflicting_deployment_environment(
    tmp_path, monkeypatch
):
    db_file = tmp_path / "bootstrap-conflict.db"
    database_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DEPLOY_ENV", "staging")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("YP_ENABLE_SQLITE_BOOTSTRAP", "1")

    with pytest.raises(RuntimeError, match="Conflicting environment"):
        create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "database_url": database_url,
                "FORCE_DB_REINIT": True,
            }
        )


def test_sqlite_bootstrap_commits_menu_and_user_alignment(tmp_path, monkeypatch):
    db_file = tmp_path / "bootstrap-commit.db"
    database_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("YP_ENABLE_SQLITE_BOOTSTRAP", "0")

    app = create_app(
        {
            "TESTING": False,
            "APP_ENV": "development",
            "SECRET_KEY": "test",
            "database_url": database_url,
            "FORCE_DB_REINIT": True,
        }
    )
    with app.app_context():
        session = get_session()
        try:
            session.execute(
                text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
            )
            session.execute(text("CREATE TABLE menus (id TEXT PRIMARY KEY)"))
            session.execute(text("INSERT INTO users(id, email) VALUES (1, 'user@test')"))
            session.execute(text("INSERT INTO menus(id) VALUES ('menu-1')"))
            session.commit()
            create_all()
        finally:
            session.close()

    with app.app_context():
        session = get_session()
        try:
            assert session.execute(
                text("SELECT is_active FROM users WHERE id=1")
            ).scalar_one() == 1
            assert session.execute(
                text("SELECT updated_at FROM menus WHERE id='menu-1'")
            ).scalar_one() is not None
        finally:
            session.close()
