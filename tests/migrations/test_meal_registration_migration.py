from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, event, text

from tests.migrations.test_residents_schedule_migration import _upgrade
from tests.migrations.test_users_updated_at_migration import (
    _assert_postgresql_database,
    _without_libpq_destination_environment,
)


LEGACY_TABLE = """
CREATE TABLE meal_registrations (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    site_id TEXT NOT NULL,
    department_id TEXT NOT NULL,
    date TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    registered INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    UNIQUE (tenant_id, site_id, department_id, date, meal_type)
)
"""


def _existing_data_roundtrip(url, monkeypatch):
    _upgrade(monkeypatch, url, "0056_residents_schedule_schema")
    engine = create_engine(url)
    with engine.begin() as conn:
        ddl = LEGACY_TABLE.replace("id INTEGER PRIMARY KEY", "id SERIAL PRIMARY KEY") if conn.dialect.name == "postgresql" else LEGACY_TABLE
        conn.execute(text(ddl))
        conn.execute(text(
            "INSERT INTO meal_registrations "
            "(id, tenant_id, site_id, department_id, date, meal_type, registered, updated_at) "
            "VALUES (9, 1, 'a', 'dep', '2026-04-06', 'lunch', 1, 'old')"
        ))
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT setval('meal_registrations_id_seq', 9)"))
    _upgrade(monkeypatch, url, "head")
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT id, tenant_id, site_id, department_id, date, meal_type, registered, updated_at "
            "FROM meal_registrations"
        )).one() == (9, 1, "a", "dep", "2026-04-06", "lunch", 1, "old")
    engine.dispose()


def test_existing_meal_registrations_survive_upgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'legacy-meals.db').as_posix()}"
    _existing_data_roundtrip(url, monkeypatch)


def test_missing_meal_unique_key_is_rejected_without_data_loss(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'invalid-meals.db').as_posix()}"
    _upgrade(monkeypatch, url, "0056_residents_schedule_schema")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(LEGACY_TABLE.replace(
            ",\n    UNIQUE (tenant_id, site_id, department_id, date, meal_type)", ""
        )))
        conn.execute(text(
            "INSERT INTO meal_registrations "
            "(id,tenant_id,site_id,department_id,date,meal_type,registered) "
            "VALUES (9,1,'a','dep','2026-04-06','lunch',1)"
        ))
    with pytest.raises(RuntimeError, match="unique key"):
        _upgrade(monkeypatch, url, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id,registered FROM meal_registrations")).one() == (9, 1)
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0056_residents_schedule_schema"
    engine.dispose()


@pytest.mark.parametrize("id_definition", ["INT PRIMARY KEY", "INTEGER PRIMARY KEY DESC"])
def test_non_rowid_sqlite_primary_key_is_rejected(tmp_path, monkeypatch, id_definition):
    url = f"sqlite:///{(tmp_path / 'non-rowid.db').as_posix()}"
    _upgrade(monkeypatch, url, "0056_residents_schedule_schema")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(LEGACY_TABLE.replace("INTEGER PRIMARY KEY", id_definition)))
        conn.execute(text(
            "INSERT INTO meal_registrations "
            "(id,tenant_id,site_id,department_id,date,meal_type,registered) "
            "VALUES (9,1,'a','dep','2026-04-06','lunch',1)"
        ))
    with pytest.raises(RuntimeError, match="rowid alias"):
        _upgrade(monkeypatch, url, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id,registered FROM meal_registrations")).one() == (9, 1)
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0056_residents_schedule_schema"
    engine.dispose()


def test_meal_upserts_are_scoped_and_do_not_issue_ddl(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'meals.db').as_posix()}"
    _upgrade(monkeypatch, url, "head")
    from core.db import init_engine
    from core.meal_registration_repo import MealRegistrationRepo

    engine = init_engine(url, force=True)
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        repo = MealRegistrationRepo()
        repo.upsert_registration(1, "a", "dep", "2026-04-06", "lunch", True)
        repo.upsert_registration(1, "a", "other", "2026-04-06", "lunch", True)
        repo.upsert_registration(1, "a", "dep", "2026-04-06", "lunch", False)
        assert repo.get_registrations_for_week(1, "a", "dep", 2026, 15)[0]["registered"] is False
        assert repo.get_registrations_for_week(1, "a", "other", 2026, 15)[0]["registered"] is True
        assert not [s for s in statements if s.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP "))]
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        engine.dispose()


def test_missing_meal_schema_is_not_an_empty_success(tmp_path):
    from core.db import init_engine
    from core.meal_registration_repo import MealRegistrationRepo
    from sqlalchemy.exc import NoSuchTableError

    engine = init_engine(f"sqlite:///{(tmp_path / 'missing.db').as_posix()}", force=True)
    try:
        with pytest.raises(NoSuchTableError):
            MealRegistrationRepo().get_registrations_for_week(1, "a", "dep", 2026, 15)
    finally:
        engine.dispose()


def test_postgresql_existing_meal_registrations(monkeypatch):
    url = os.environ.get("SEC_PG_07_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SEC_PG_07_TEST_DATABASE_URL to an empty isolated PostgreSQL test database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(url, require_empty=True)
        _existing_data_roundtrip(url, monkeypatch)


def test_postgresql_missing_id_generator_is_rejected_atomically(monkeypatch):
    url = os.environ.get("SEC_PG_07_BAD_MEAL_DATABASE_URL")
    if not url:
        pytest.skip("Set SEC_PG_07_BAD_MEAL_DATABASE_URL to an empty isolated PostgreSQL test database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(url, require_empty=True)
        _upgrade(monkeypatch, url, "0056_residents_schedule_schema")
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(text(LEGACY_TABLE))
            conn.execute(text(
                "INSERT INTO meal_registrations "
                "(id,tenant_id,site_id,department_id,date,meal_type,registered) "
                "VALUES (9,1,'a','dep','2026-04-06','lunch',1)"
            ))
        with pytest.raises(RuntimeError, match="id must be generated"):
            _upgrade(monkeypatch, url, "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT id,registered FROM meal_registrations")).one() == (9, 1)
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0056_residents_schedule_schema"
        engine.dispose()
