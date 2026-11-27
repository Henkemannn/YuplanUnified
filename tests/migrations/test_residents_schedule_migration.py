from __future__ import annotations

from pathlib import Path
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy import event

from tests.migrations.test_users_updated_at_migration import (
    _assert_postgresql_database,
    _without_libpq_destination_environment,
)


ROOT = Path(__file__).resolve().parents[2]


def _upgrade(monkeypatch, url, revision):
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, revision)


def _legacy_table(conn):
    conn.execute(text(
        "CREATE TABLE department_residents_schedule ("
        "department_id TEXT NOT NULL, week INTEGER, weekday INTEGER NOT NULL, "
        "meal TEXT NOT NULL, count INTEGER NOT NULL, "
        "PRIMARY KEY(department_id, week, weekday, meal))"
    ))


def test_existing_schedule_rows_and_forever_upsert_survive_migration(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'residents.db').as_posix()}"
    _upgrade(monkeypatch, url, "0055_weekview_schema")
    engine = create_engine(url)
    with engine.begin() as conn:
        _legacy_table(conn)
        conn.execute(text(
            "INSERT INTO department_residents_schedule VALUES "
            "('dep', NULL, 1, 'lunch', 0), ('dep', 12, 1, 'lunch', 5)"
        ))
    _upgrade(monkeypatch, url, "head")
    from core.db import init_engine
    from core.residents_schedule_repo import ResidentsScheduleRepo
    from core.residents_weekly_repo import ResidentsWeeklyRepo
    from core.weekview.service import resolve_effective_resident_counts_for_day

    init_engine(url, force=True)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO sites(id, name) VALUES ('site', 'Test')"))
        conn.execute(text(
            "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) "
            "VALUES ('dep', 'site', 'Test', 'fixed', 10)"
        ))
    repo = ResidentsScheduleRepo()
    assert repo.get_forever("dep") == [{"weekday": 1, "meal": "lunch", "count": 0}]
    repo.upsert_items("dep", None, [{"weekday": 1, "meal": "lunch", "count": 3}])
    repo.upsert_items("dep", None, [{"weekday": 1, "meal": "lunch", "count": 0}])
    repo.upsert_items("dep", 12, [{"weekday": 1, "meal": "lunch", "count": 7}])
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT week, count FROM department_residents_schedule ORDER BY week"
        )).all()
    assert rows == [(None, 0), (12, 7)]
    assert resolve_effective_resident_counts_for_day("dep", 2026, 12, 1)["lunch"] == 7
    repo.delete_week("dep", 12)
    assert resolve_effective_resident_counts_for_day("dep", 2026, 12, 1)["lunch"] == 0
    repo.delete_forever("dep")
    ResidentsWeeklyRepo().upsert_for_week("dep", 2026, 12, 0, None)
    assert resolve_effective_resident_counts_for_day("dep", 2026, 12, 1) == {
        "lunch": 0, "dinner": 10, "source": "weekly_override"
    }
    engine.dispose()


def test_duplicate_forever_rows_fail_before_schema_changes(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'duplicates.db').as_posix()}"
    _upgrade(monkeypatch, url, "0055_weekview_schema")
    engine = create_engine(url)
    with engine.begin() as conn:
        _legacy_table(conn)
        conn.execute(text(
            "INSERT INTO department_residents_schedule VALUES "
            "('dep', NULL, 1, 'lunch', 0), ('dep', NULL, 1, 'lunch', 1)"
        ))
    with pytest.raises(RuntimeError, match="Ambiguous duplicate residents rows"):
        _upgrade(monkeypatch, url, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM department_residents_schedule")).scalar_one() == 2
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
        assert conn.execute(text(
            "SELECT count(*) FROM sqlite_master WHERE name='ux_residents_schedule_forever'"
        )).scalar_one() == 0
    engine.dispose()


@pytest.mark.parametrize("column", ["department_id", "weekday", "meal", "count"])
def test_nullable_schedule_required_columns_fail_without_changes(tmp_path, monkeypatch, column):
    url = f"sqlite:///{(tmp_path / 'nullable.db').as_posix()}"
    _upgrade(monkeypatch, url, "0055_weekview_schema")
    engine = create_engine(url)
    definitions = {
        "department_id": "TEXT NOT NULL", "week": "INTEGER", "weekday": "INTEGER NOT NULL",
        "meal": "TEXT NOT NULL", "count": "INTEGER NOT NULL",
    }
    definitions[column] = definitions[column].replace(" NOT NULL", "")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE department_residents_schedule (" +
                          ", ".join(f"{name} {definition}" for name, definition in definitions.items()) + ")"))
        conn.execute(text("INSERT INTO department_residents_schedule VALUES ('dep', NULL, 1, 'lunch', 0)"))
    with pytest.raises(RuntimeError, match="Incompatible residents schema"):
        _upgrade(monkeypatch, url, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT * FROM department_residents_schedule")).all() == [
            ("dep", None, 1, "lunch", 0)
        ]
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
        assert not conn.execute(text(
            "SELECT name FROM sqlite_master WHERE name LIKE 'ux_residents_schedule_%'"
        )).all()
    engine.dispose()


@pytest.mark.parametrize("column", ["department_id", "year", "week"])
def test_nullable_weekly_key_fails_before_schedule_changes(tmp_path, monkeypatch, column):
    url = f"sqlite:///{(tmp_path / 'weekly-nullable.db').as_posix()}"
    _upgrade(monkeypatch, url, "0055_weekview_schema")
    engine = create_engine(url)
    definitions = {
        "id": "TEXT PRIMARY KEY", "department_id": "TEXT NOT NULL", "year": "INTEGER NOT NULL",
        "week": "INTEGER NOT NULL", "residents_lunch": "INTEGER", "residents_dinner": "INTEGER",
        "updated_at": "TEXT",
    }
    definitions[column] = definitions[column].replace(" NOT NULL", "")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE department_residents_weekly (" +
                          ", ".join(f"{name} {definition}" for name, definition in definitions.items()) + ")"))
        conn.execute(text("INSERT INTO department_residents_weekly VALUES ('id', 'dep', 2026, 12, 0, NULL, NULL)"))
    with pytest.raises(RuntimeError, match="Incompatible residents schema"):
        _upgrade(monkeypatch, url, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT residents_lunch, residents_dinner FROM department_residents_weekly")).one() == (0, None)
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
        assert not conn.execute(text(
            "SELECT name FROM sqlite_master WHERE name='department_residents_schedule'"
        )).all()
    engine.dispose()


def test_invalid_sqlite_schedule_value_fails_without_changes(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'invalid-value.db').as_posix()}"
    _upgrade(monkeypatch, url, "0055_weekview_schema")
    engine = create_engine(url)
    with engine.begin() as conn:
        _legacy_table(conn)
        conn.execute(text("INSERT INTO department_residents_schedule VALUES ('dep', NULL, 1, 'lunch', 'invalid')"))
    with pytest.raises(RuntimeError, match="Incompatible residents"):
        _upgrade(monkeypatch, url, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count FROM department_residents_schedule")).scalar_one() == "invalid"
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
    engine.dispose()


def test_postgresql_nullable_schedule_is_rejected_atomically(monkeypatch):
    url = os.environ.get("SEC_PG_07_BAD_RESIDENT_DATABASE_URL")
    if not url:
        pytest.skip("Set SEC_PG_07_BAD_RESIDENT_DATABASE_URL to an empty isolated PostgreSQL test database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(url, require_empty=True)
        _upgrade(monkeypatch, url, "0055_weekview_schema")
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE department_residents_schedule (department_id TEXT, week INTEGER, "
                "weekday INTEGER NOT NULL, meal TEXT NOT NULL, count INTEGER)"
            ))
            conn.execute(text(
                "INSERT INTO department_residents_schedule VALUES ('dep', NULL, 1, 'lunch', NULL)"
            ))
        with pytest.raises(RuntimeError, match="Incompatible residents schema"):
            _upgrade(monkeypatch, url, "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT * FROM department_residents_schedule")).one() == (
                "dep", None, 1, "lunch", None
            )
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
            assert not conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
                "AND indexname LIKE 'ux_residents_schedule_%'"
            )).all()
        engine.dispose()


def test_postgresql_existing_schedule_and_boolean_completion(monkeypatch):
    url = os.environ.get("SEC_PG_06_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SEC_PG_06_TEST_DATABASE_URL to an empty isolated PostgreSQL test database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(url, require_empty=True)
        _upgrade(monkeypatch, url, "0055_weekview_schema")
        engine = create_engine(url)
        with engine.begin() as conn:
            _legacy_table(conn)
            conn.execute(text("INSERT INTO department_residents_schedule VALUES ('dep', 12, 1, 'lunch', 5)"))
            conn.execute(text("INSERT INTO sites(id, name) VALUES ('site', 'Test')"))
            conn.execute(text(
                "INSERT INTO departments(id, site_id, name, resident_count_mode) "
                "VALUES ('dep', 'site', 'Test', 'fixed')"
            ))
            conn.execute(text(
                "INSERT INTO department_requirement_groups(id,department_id,label,default_quantity,is_active) "
                "VALUES ('grp','dep','Test',1,true)"
            ))
        _upgrade(monkeypatch, url, "head")
        from core.db import init_engine
        from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
        from core.residents_schedule_repo import ResidentsScheduleRepo
        from core.weekview.service import WeekviewService

        app_engine = init_engine(url, force=True)
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(app_engine, "before_cursor_execute", capture)
        try:
            repo = ResidentsScheduleRepo()
            repo.upsert_items("dep", None, [{"weekday": 1, "meal": "lunch", "count": 0}])
            repo.upsert_items("dep", None, [{"weekday": 1, "meal": "lunch", "count": 4}])
            repo.upsert_items("dep", 12, [{"weekday": 1, "meal": "lunch", "count": 7}])
            completion = DepartmentRequirementGroupCompletionRepo()
            assert completion.set_marked("dep", "grp", "2026-09-21", "lunch", True)["marked"] is True
            assert completion.set_marked("dep", "grp", "2026-09-21", "lunch", False)["marked"] is False
            assert repo.get_forever("dep") == [{"weekday": 1, "meal": "lunch", "count": 4}]
            assert repo.get_week("dep", 12) == [{"weekday": 1, "meal": "lunch", "count": 7}]
            service = WeekviewService()
            _, etag = service.fetch_weekview(1, 2026, 12, "dep", "site")
            assert service.fetch_weekview_conditional(1, 2026, 12, "dep", etag, "site")[0] is True
            with engine.connect() as conn:
                assert conn.execute(text("SELECT count(*) FROM department_residents_schedule")).scalar_one() == 2
                assert conn.execute(text("SELECT marked FROM department_requirement_group_completions")).scalar_one() is False
            assert not [s for s in statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]
        finally:
            event.remove(app_engine, "before_cursor_execute", capture)
            engine.dispose()
