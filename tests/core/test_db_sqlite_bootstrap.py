from __future__ import annotations

from sqlalchemy import inspect

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
