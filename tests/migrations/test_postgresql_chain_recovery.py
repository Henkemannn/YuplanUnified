from __future__ import annotations

import importlib
import os

import pytest
from alembic import command
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine

from core.weekview.schema import WEEKVIEW_TABLES, verify_weekview_schema
from tests.migrations.test_users_updated_at_migration import (
    _assert_data_preserved,
    _assert_postgresql_database,
    _assert_revision,
    _assert_users_contract,
    _config,
    _seed_users_and_references,
    _snapshot_data,
    _upgrade,
    _without_libpq_destination_environment,
)


@pytest.fixture(params=("sqlite", "postgresql"))
def migration_connection(request):
    database_url = os.getenv("SEC_PG_TEST_DATABASE_URL")
    if request.param == "postgresql" and not database_url:
        pytest.skip("Set SEC_PG_TEST_DATABASE_URL to an empty isolated PostgreSQL database")
    with _without_libpq_destination_environment():
        if request.param == "postgresql":
            _assert_postgresql_database(database_url, require_empty=True)
            engine = create_engine(database_url)
        else:
            engine = create_engine("sqlite://")
        try:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    if request.param == "postgresql":
                        connection.exec_driver_sql("CREATE SCHEMA sec_pg04_fixture")
                        connection.exec_driver_sql("SET LOCAL search_path TO sec_pg04_fixture")
                    yield connection
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()


def _create_menu_fixture(connection, *, site_tenants=None, menus=()):
    connection.exec_driver_sql(
        "CREATE TABLE menus (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, "
        "year INTEGER NOT NULL, week INTEGER NOT NULL)"
    )
    if site_tenants == "missing_tenant":
        connection.exec_driver_sql("CREATE TABLE sites (id TEXT PRIMARY KEY)")
    elif site_tenants is not None:
        connection.exec_driver_sql("CREATE TABLE sites (id TEXT PRIMARY KEY, tenant_id INTEGER)")
        for site_id, tenant_id in site_tenants:
            connection.execute(
                text("INSERT INTO sites (id, tenant_id) VALUES (:site, :tenant)"),
                {"site": site_id, "tenant": tenant_id},
            )
    for menu_id, tenant_id in menus:
        connection.execute(
            text("INSERT INTO menus (id, tenant_id, year, week) VALUES (:id, :tenant, 2034, 1)"),
            {"id": menu_id, "tenant": tenant_id},
        )


def _upgrade_menu_site(connection):
    migration = importlib.import_module("migrations.versions.0002_add_site_id_to_menus")
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()


def test_menu_site_empty_database(migration_connection):
    _create_menu_fixture(migration_connection)
    _upgrade_menu_site(migration_connection)
    assert "site_id" in {
        column["name"] for column in inspect(migration_connection).get_columns("menus")
    }


@pytest.mark.parametrize("site_tenants", [None, "missing_tenant", [], [("a", 1), ("b", 1)]])
def test_menu_site_ambiguous_data_fails_closed(migration_connection, site_tenants):
    _create_menu_fixture(migration_connection, site_tenants=site_tenants, menus=[(10, 1)])
    with pytest.raises(RuntimeError, match="Cannot safely map existing menus"):
        _upgrade_menu_site(migration_connection)
    assert "site_id" not in {
        column["name"] for column in inspect(migration_connection).get_columns("menus")
    }
    assert migration_connection.execute(text("SELECT id, tenant_id FROM menus")).one() == (10, 1)


def test_menu_site_unique_tenant_mapping(migration_connection):
    _create_menu_fixture(
        migration_connection,
        site_tenants=[("site-a", 1), ("site-b", 2)],
        menus=[(10, 1), (20, 2)],
    )
    _upgrade_menu_site(migration_connection)
    assert migration_connection.execute(
        text("SELECT id, tenant_id, site_id FROM menus ORDER BY id")
    ).all() == [(10, 1, "site-a"), (20, 2, "site-b")]


def test_postgresql_chain_recovery(monkeypatch):
    database_url = os.getenv("SEC_PG_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set SEC_PG_TEST_DATABASE_URL to an empty isolated PostgreSQL database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(database_url, require_empty=True)
        monkeypatch.setenv("DATABASE_URL", database_url)
        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE alembic_version (version_num INTEGER PRIMARY KEY)"
                )
            with pytest.raises(RuntimeError, match="version_num must be a string"):
                _upgrade(database_url, "0012_add_user_fields")
            with engine.begin() as connection:
                assert inspect(connection).get_table_names() == ["alembic_version"]
                connection.exec_driver_sql("DROP TABLE alembic_version")
        finally:
            engine.dispose()
        _upgrade(database_url, "0012_add_user_fields")
        engine = create_engine(database_url)
        try:
            _seed_users_and_references(engine)
            before = _snapshot_data(engine)
            with engine.begin() as connection:
                length = inspect(connection).get_columns("alembic_version")[0]["type"].length
                longest = max(len(item.revision) for item in ScriptDirectory.from_config(
                    _config(database_url)
                ).walk_revisions())
                assert length >= longest
                connection.exec_driver_sql(
                    "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32)"
                )
            _upgrade(database_url, "0014_add_residences_and_department_residence")
            with engine.connect() as connection:
                assert inspect(connection).get_columns("alembic_version")[0]["type"].length >= longest
            _upgrade(database_url, "0032_add_department_menu_choices")
            _upgrade(database_url, "0033_add_users_department_id")
            _assert_data_preserved(engine, before)
            with engine.connect() as connection:
                _assert_users_contract(connection)
                assert any(
                    fk["constrained_columns"] == ["department_id"]
                    and fk["referred_table"] == "departments"
                    and fk["referred_columns"] == ["id"]
                    for fk in inspect(connection).get_foreign_keys("users")
                )
            _upgrade(database_url, "0050_add_password_reset_storage")
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO sites(id, name) VALUES ('site-9101', 'Test site')"))
                connection.execute(text(
                    "INSERT INTO menus(id, tenant_id, site_id, year, week) "
                    "VALUES (9101, 1, 'site-9101', 2034, 1)"
                ))
                connection.execute(text(
                    "INSERT INTO dishes(id, tenant_id, name) VALUES (9101, 1, 'Synthetic')"
                ))
                connection.execute(text(
                    "INSERT INTO menu_variants(id, menu_id, day, meal, variant_type, dish_id) "
                    "VALUES (9101, 9101, 'mon', 'lunch', 'main', 9101)"
                ))
                connection.execute(text(
                    "INSERT INTO tenants(id, name, active) VALUES (9102, 'Other tenant', true)"
                ))
                connection.execute(text(
                    "INSERT INTO menus(id, tenant_id, site_id, year, week) "
                    "VALUES (9102, 9102, 'site-9101', 2034, 1)"
                ))
            with pytest.raises(RuntimeError, match="invalid menu tenant/site relations"):
                _upgrade(database_url, "0051_add_site_scoped_menu_uniqueness")
            _assert_revision(engine, "0050_add_password_reset_storage")
            with engine.begin() as connection:
                assert "tenant_id" not in {
                    column["name"] for column in inspect(connection).get_columns("sites")
                }
                assert connection.execute(text(
                    "SELECT count(*) FROM menus WHERE id IN (9101, 9102)"
                )).scalar_one() == 2
                connection.execute(text("DELETE FROM menus WHERE id=9102"))
                connection.execute(text("DELETE FROM tenants WHERE id=9102"))
            _upgrade(database_url, "0054_add_menu_import_guards")
            _assert_revision(engine, "0054_add_menu_import_guards")
            _assert_data_preserved(engine, before)
            with engine.connect() as connection:
                assert connection.execute(text(
                    "SELECT menu_id, dish_id FROM menu_variants WHERE id=9101"
                )).one() == (9101, 9101)
                assert connection.execute(text(
                    "SELECT site_id FROM dishes WHERE id=9101"
                )).scalar_one() == "site-9101"
                assert ("tenant_id", "site_id", "year", "week") in {
                    tuple(item["column_names"])
                    for item in inspect(connection).get_unique_constraints("menus")
                }
            _upgrade(database_url, "0055_weekview_schema")
            _assert_revision(engine, "0055_weekview_schema")
            with engine.connect() as connection:
                verify_weekview_schema(connection)
                triggers = set(connection.execute(text(
                    "SELECT c.relname, t.tgname FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid=t.tgrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname=current_schema() AND NOT t.tgisinternal"
                )).all())
                for table in WEEKVIEW_TABLES:
                    assert (table, f"trg_{table}_updated_at_v2") in triggers
                    if table != "weekview_versions":
                        assert (table, f"trg_{table}_bump_version_v2") in triggers
            _upgrade(database_url, "head")
            _assert_revision(engine, "0059_normal_exclusions_scope")
            _assert_data_preserved(engine, before)
            with engine.connect() as connection:
                menu_before = connection.execute(text(
                    "SELECT menu_id, dish_id FROM menu_variants WHERE id=9101"
                )).one()
                assert menu_before == (9101, 9101)
                tables_before = inspect(connection).get_table_names()

            statements = []

            def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
                statements.append(statement)

            event.listen(Engine, "before_cursor_execute", capture)
            try:
                _upgrade(database_url, "head")
            finally:
                event.remove(Engine, "before_cursor_execute", capture)
            assert not [
                statement for statement in statements
                if statement.lstrip().upper().startswith(
                    ("CREATE ", "ALTER ", "DROP ", "INSERT ", "UPDATE ", "DELETE ")
                )
            ]
            _assert_revision(engine, "0059_normal_exclusions_scope")
            _assert_data_preserved(engine, before)
            with engine.connect() as connection:
                assert connection.execute(text(
                    "SELECT menu_id, dish_id FROM menu_variants WHERE id=9101"
                )).one() == menu_before
                assert inspect(connection).get_table_names() == tables_before
        finally:
            engine.dispose()
