from __future__ import annotations

from contextlib import contextmanager
import ipaddress
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError


ROOT = Path(__file__).resolve().parents[2]
REVISION = "778407d29f47"
PREVIOUS_REVISION = "0012_add_user_fields"


def _config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _is_postgresql_url(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "postgresql"


_LIBPQ_DESTINATION_ENVIRONMENT = (
    "PGDATABASE",
    "PGHOST",
    "PGHOSTADDR",
    "PGOPTIONS",
    "PGPORT",
    "PGSERVICE",
    "PGSERVICEFILE",
)


def _validate_postgresql_url(database_url: str) -> URL:
    parsed = make_url(database_url)
    assert parsed.get_backend_name() == "postgresql"
    assert not parsed.query
    assert parsed.host in {"localhost", "127.0.0.1", "::1"}
    assert parsed.port is not None
    assert parsed.database is not None
    assert parsed.database.startswith("sec_pg_03")
    return parsed


@contextmanager
def _without_libpq_destination_environment():
    previous = {
        name: os.environ.pop(name)
        for name in _LIBPQ_DESTINATION_ENVIRONMENT
        if name in os.environ
    }
    try:
        yield
    finally:
        os.environ.update(previous)


def _assert_postgresql_database(database_url: str, *, require_empty: bool = False) -> None:
    parsed = _validate_postgresql_url(database_url)

    with _without_libpq_destination_environment():
        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                assert connection.dialect.name == "postgresql"
                server_address, server_port, database_name, schema_name = connection.execute(
                    text(
                        "SELECT host(inet_server_addr()), inet_server_port(), "
                        "current_database(), current_schema()"
                    )
                ).one()
                assert ipaddress.ip_address(server_address).is_loopback
                if parsed.host != "localhost":
                    assert server_address == str(ipaddress.ip_address(parsed.host))
                assert server_port == parsed.port
                assert database_name == parsed.database
                assert schema_name == "public"
                if require_empty:
                    assert inspect(connection).get_table_names(schema="public") == []
                    assert connection.execute(
                        text(
                            "SELECT count(*) "
                            "FROM pg_namespace "
                            "WHERE nspname NOT LIKE 'pg_%' "
                            "AND nspname <> 'information_schema' "
                            "AND nspname <> 'public'"
                        )
                    ).scalar_one() == 0
                    assert connection.execute(
                        text(
                            "SELECT count(*) "
                            "FROM pg_class AS relation "
                            "JOIN pg_namespace AS schema "
                            "ON schema.oid = relation.relnamespace "
                            "WHERE schema.nspname NOT LIKE 'pg_%' "
                            "AND schema.nspname <> 'information_schema' "
                            "AND relation.relkind IN "
                            "('r', 'p', 'v', 'm', 'f', 'S')"
                        )
                    ).scalar_one() == 0
        finally:
            engine.dispose()


def _upgrade(database_url: str, revision: str) -> None:
    _run_alembic(database_url, command.upgrade, revision)


def _downgrade(database_url: str, revision: str) -> None:
    _run_alembic(database_url, command.downgrade, revision)


def _run_alembic(database_url: str, action, revision: str) -> None:
    if _is_postgresql_url(database_url):
        _assert_postgresql_database(database_url)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        if _is_postgresql_url(database_url):
            with _without_libpq_destination_environment():
                action(_config(database_url), revision)
        else:
            action(_config(database_url), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _assert_users_contract(connection) -> None:
    inspector = inspect(connection)
    primary_key = inspector.get_pk_constraint("users")
    assert primary_key["constrained_columns"] == ["id"]

    def foreign_keys(table_name: str) -> set[tuple[tuple[str, ...], str, tuple[str, ...]]]:
        return {
            (
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
                tuple(foreign_key["referred_columns"]),
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        }

    assert (("tenant_id",), "tenants", ("id",)) in foreign_keys("users")
    assert (("unit_id",), "units", ("id",)) in foreign_keys("users")
    assert (("sender_user_id",), "users", ("id",)) in foreign_keys("messages")
    assert (("user_id",), "users", ("id",)) in foreign_keys("notes")
    assert (("assignee_id",), "users", ("id",)) in foreign_keys("tasks")
    assert (("creator_user_id",), "users", ("id",)) in foreign_keys("tasks")


def _seed_users_and_references(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants (id, name, active) "
                "VALUES (1, 'SEC-PG-03', true) ON CONFLICT (id) DO NOTHING"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, tenant_id, email, password_hash, role, username, full_name) "
                "VALUES (9101, 1, 'sec-pg-03@example.test', 'hash', 'admin', "
                "'sec-pg-03', 'SEC-PG-03')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO messages "
                "(tenant_id, sender_user_id, audience_type, subject, body) "
                "VALUES (1, 9101, 'user', 'SEC-PG-03', 'synthetic')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notes (tenant_id, user_id, content) "
                "VALUES (1, 9101, 'synthetic')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks "
                "(tenant_id, task_type, title, assignee_id, creator_user_id) "
                "VALUES (1, 'SEC-PG-03', 'SEC-PG-03', 9101, 9101)"
            )
        )


def _snapshot_data(engine) -> dict[str, tuple]:
    with engine.connect() as connection:
        return {
            "users": connection.execute(
                text(
                    "SELECT id, tenant_id, email, password_hash, role, username, full_name "
                    "FROM users WHERE id = 9101"
                )
            ).one(),
            "messages": connection.execute(
                text(
                    "SELECT tenant_id, sender_user_id, audience_type, subject, body "
                    "FROM messages WHERE sender_user_id = 9101"
                )
            ).one(),
            "notes": connection.execute(
                text(
                    "SELECT tenant_id, user_id, content FROM notes WHERE user_id = 9101"
                )
            ).one(),
            "tasks": connection.execute(
                text(
                    "SELECT tenant_id, task_type, title, assignee_id, creator_user_id "
                    "FROM tasks WHERE assignee_id = 9101 AND creator_user_id = 9101"
                )
            ).one(),
        }


def _assert_data_preserved(engine, expected: dict[str, tuple]) -> None:
    assert _snapshot_data(engine) == expected


def _assert_revision(engine, expected: str) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == expected


def _assert_updated_at_contract(connection) -> None:
    column = {
        item["name"]: item for item in inspect(connection).get_columns("users")
    }["updated_at"]
    assert any(marker in str(column["type"]).upper() for marker in ("DATE", "TIME"))
    assert column["nullable"] is True
    assert "CURRENT_TIMESTAMP" in str(column["default"]).upper()


def _assert_invalid_user_reference_rejected(engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO messages "
                    "(tenant_id, sender_user_id, audience_type, subject, body) "
                    "VALUES (1, 999999, 'user', 'invalid', 'invalid')"
                )
            )


def _assert_migrated_users(engine, expected: dict[str, tuple]) -> None:
    with engine.connect() as connection:
        _assert_updated_at_contract(connection)
        _assert_users_contract(connection)
    _assert_data_preserved(engine, expected)
    if engine.dialect.name == "postgresql":
        _assert_invalid_user_reference_rejected(engine)


def _run_regression(database_url: str) -> None:
    _upgrade(database_url, PREVIOUS_REVISION)
    engine = create_engine(database_url)
    try:
        _seed_users_and_references(engine)
        before = _snapshot_data(engine)
        _assert_revision(engine, PREVIOUS_REVISION)
    finally:
        engine.dispose()

    _upgrade(database_url, REVISION)
    engine = create_engine(database_url)
    try:
        _assert_revision(engine, REVISION)
        _assert_migrated_users(engine, before)
    finally:
        engine.dispose()

    _downgrade(database_url, PREVIOUS_REVISION)
    engine = create_engine(database_url)
    try:
        _assert_revision(engine, PREVIOUS_REVISION)
        with engine.connect() as connection:
            assert "updated_at" not in {
                column["name"] for column in inspect(connection).get_columns("users")
            }
            _assert_users_contract(connection)
        _assert_data_preserved(engine, before)
    finally:
        engine.dispose()

    _upgrade(database_url, REVISION)
    engine = create_engine(database_url)
    try:
        _assert_revision(engine, REVISION)
        _assert_migrated_users(engine, before)
    finally:
        engine.dispose()


def test_users_updated_at_sqlite_regression(tmp_path):
    _run_regression(f"sqlite:///{(tmp_path / 'users-updated-at.db').as_posix()}")


def test_postgresql_connection_guard_rejects_host_override():
    with pytest.raises(AssertionError):
        _validate_postgresql_url(
            "postgresql+psycopg://postgres@127.0.0.1:55445/"
            "sec_pg_03r_test?host=192.0.2.1"
        )


def test_postgresql_connection_guard_rejects_search_path_override():
    with pytest.raises(AssertionError):
        _validate_postgresql_url(
            "postgresql+psycopg://postgres@127.0.0.1:55445/"
            "sec_pg_03r_test?options=-csearch_path%3Dattacker"
        )


def test_users_updated_at_postgresql_regression():
    database_url = os.getenv("SEC_PG_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set SEC_PG_TEST_DATABASE_URL to an isolated PostgreSQL database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(database_url, require_empty=True)
        _run_regression(database_url)
