import hashlib
import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from core.admin_repo import NotesRepo
from core.etag import ConcurrencyError
from core.notes_version_trigger import (
    NOTES_VERSION_BUMP_TRIGGER_NAME,
    NOTES_VERSION_BUMP_TRIGGER_SHA256,
    NOTES_VERSION_BUMP_TRIGGER_SQL,
)
from tests.migrations.test_users_updated_at_migration import (
    _without_libpq_destination_environment,
)

ROOT = Path(__file__).resolve().parents[2]


def _config(target: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{target}")
    return config


def _notes_trigger_sql(connection) -> str | None:
    return connection.execute(
        text(
            "SELECT sql FROM sqlite_master "
            "WHERE type='trigger' AND name=:name"
        ),
        {"name": NOTES_VERSION_BUMP_TRIGGER_NAME},
    ).scalar_one_or_none()


def _notes_row(connection) -> dict:
    row = connection.execute(text("SELECT * FROM notes")).mappings().one()
    return dict(row)


def test_notes_site_migration_preserves_legacy_rows_and_supports_downgrade(
    tmp_path, monkeypatch
):
    target = tmp_path / "notes-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _config(target)
    command.upgrade(config, "0051_add_site_scoped_menu_uniqueness")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"DROP TRIGGER IF EXISTS {NOTES_VERSION_BUMP_TRIGGER_NAME}"
            )
            connection.execute(
                text("INSERT INTO tenants(id, name, active) VALUES (9701, 'Notes Tenant', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO users(id, tenant_id, email, password_hash, role) "
                    "VALUES (9701, 9701, 'notes@example.test', 'hash', 'admin')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id) "
                    "VALUES ('notes-site', 'Notes Site', 9701)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO notes(tenant_id, user_id, content, private_flag) "
                    "VALUES (9701, 9701, 'legacy', 0)"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "0052_add_site_id_to_notes")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            assert _notes_trigger_sql(connection) is None
            row = connection.execute(
                text("SELECT content, site_id FROM notes")
            ).one()
            assert row == ("legacy", None)
    finally:
        engine.dispose()

    command.upgrade(config, "0052_add_site_id_to_notes")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            assert _notes_trigger_sql(connection) is None
            assert connection.execute(
                text("SELECT content, site_id FROM notes")
            ).one() == ("legacy", None)
    finally:
        engine.dispose()

    command.downgrade(config, "0051_add_site_scoped_menu_uniqueness")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" not in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            assert connection.execute(
                text("SELECT content FROM notes")
            ).scalar_one() == "legacy"
    finally:
        engine.dispose()


def test_notes_trigger_survives_upgrade_downgrade_and_reupgrade(
    tmp_path, monkeypatch
):
    target = tmp_path / "notes-trigger-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _config(target)
    command.upgrade(config, "0051_add_site_scoped_menu_uniqueness")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO tenants(id, name, active) VALUES (9702, 'Trigger Tenant', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO users(id, tenant_id, email, password_hash, role) "
                    "VALUES (9702, 9702, 'trigger@example.test', 'hash', 'admin')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id) "
                    "VALUES ('trigger-site', 'Trigger Site', 9702)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO notes(tenant_id, user_id, content, private_flag) "
                    "VALUES (9702, 9702, 'preserve me', 1)"
                )
            )
            trigger_sql = _notes_trigger_sql(connection)
            assert trigger_sql is not None
            assert hashlib.sha256(trigger_sql.encode("utf-8")).hexdigest() == (
                NOTES_VERSION_BUMP_TRIGGER_SHA256
            )
            connection.execute(
                text(
                    "UPDATE notes SET updated_at='2000-01-01 00:00:00' "
                    "WHERE tenant_id=9702"
                )
            )
            changed = connection.execute(
                text(
                    "UPDATE notes SET content='triggered once' "
                    "WHERE tenant_id=9702"
                )
            ).rowcount
            assert changed == 1
            before = _notes_row(connection)
            assert before["version"] == 2
            assert before["updated_at"] != "2000-01-01 00:00:00"
            assert _notes_trigger_sql(connection) is not None
    finally:
        engine.dispose()

    command.upgrade(config, "0052_add_site_id_to_notes")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            trigger_sql = _notes_trigger_sql(connection)
            assert trigger_sql is not None
            assert hashlib.sha256(trigger_sql.encode("utf-8")).hexdigest() == (
                NOTES_VERSION_BUMP_TRIGGER_SHA256
            )
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "0052_add_site_id_to_notes"
            migrated = _notes_row(connection)
            before.pop("site_id", None)
            assert {key: migrated[key] for key in before} == before
            assert migrated["site_id"] is None
    finally:
        engine.dispose()

    runtime_engine = create_engine(f"sqlite:///{target}")
    monkeypatch.setattr(
        "core.admin_repo.get_session",
        lambda: Session(runtime_engine),
    )
    try:
        NotesRepo().touch(before["id"], expected_version=2)
        with runtime_engine.connect() as connection:
            row = _notes_row(connection)
            assert row["version"] == 3
            assert row["updated_at"] != "2000-01-01 00:00:00"
        try:
            NotesRepo().touch(before["id"], expected_version=2)
        except ConcurrencyError:
            pass
        else:
            raise AssertionError("stale notes version was accepted")
        with runtime_engine.connect() as connection:
            assert _notes_row(connection) == row
    finally:
        runtime_engine.dispose()

    command.downgrade(config, "0051_add_site_scoped_menu_uniqueness")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert "site_id" not in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            trigger_sql = _notes_trigger_sql(connection)
            assert trigger_sql is not None
            assert hashlib.sha256(trigger_sql.encode("utf-8")).hexdigest() == (
                NOTES_VERSION_BUMP_TRIGGER_SHA256
            )
            assert _notes_row(connection)["version"] == 3
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "0051_add_site_scoped_menu_uniqueness"
    finally:
        engine.dispose()

    command.upgrade(config, "0052_add_site_id_to_notes")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert _notes_trigger_sql(connection) == NOTES_VERSION_BUMP_TRIGGER_SQL
            assert _notes_row(connection)["version"] == 3
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "0052_add_site_id_to_notes"
    finally:
        engine.dispose()


def test_notes_trigger_absent_remains_absent_and_repo_bumps_once(
    tmp_path, monkeypatch
):
    target = tmp_path / "notes-trigger-absent.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _config(target)
    command.upgrade(config, "0051_add_site_scoped_menu_uniqueness")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"DROP TRIGGER IF EXISTS {NOTES_VERSION_BUMP_TRIGGER_NAME}"
            )
            connection.execute(
                text("INSERT INTO tenants(id, name, active) VALUES (9703, 'No Trigger Tenant', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO users(id, tenant_id, email, password_hash, role) "
                    "VALUES (9703, 9703, 'no-trigger@example.test', 'hash', 'admin')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO notes(tenant_id, user_id, content, private_flag) "
                    "VALUES (9703, 9703, 'no trigger', 0)"
                )
            )
            note_id = connection.execute(
                text("SELECT id FROM notes WHERE tenant_id=9703")
            ).scalar_one()
    finally:
        engine.dispose()

    command.upgrade(config, "0052_add_site_id_to_notes")
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert _notes_trigger_sql(connection) is None
            assert _notes_row(connection)["version"] == 0
    finally:
        engine.dispose()

    runtime_engine = create_engine(f"sqlite:///{target}")
    monkeypatch.setattr(
        "core.admin_repo.get_session",
        lambda: Session(runtime_engine),
    )
    try:
        NotesRepo().touch(note_id, expected_version=0)
        with runtime_engine.connect() as connection:
            assert _notes_row(connection)["version"] == 1
    finally:
        runtime_engine.dispose()


def test_notes_touch_without_expected_version_is_scoped_on_sqlite(
    tmp_path, monkeypatch
):
    target = tmp_path / "notes-touch-scope.db"
    database_url = f"sqlite:///{target}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _config(target)
    command.upgrade(config, "0051_add_site_scoped_menu_uniqueness")

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO tenants(id, name, active) VALUES (9706, 'Touch Tenant', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO users(id, tenant_id, email, password_hash, role) "
                    "VALUES (9706, 9706, 'touch@example.test', 'hash', 'admin')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO notes(tenant_id, user_id, content, updated_at, version) "
                    "VALUES (9706, 9706, 'target', '2000-01-01 00:00:00', 0), "
                    "(9706, 9706, 'other', '2000-01-01 00:00:00', 0)"
                )
            )
            note_ids = connection.execute(
                text("SELECT id FROM notes WHERE tenant_id=9706 ORDER BY id")
            ).scalars().all()
    finally:
        engine.dispose()

    command.upgrade(config, "0052_add_site_id_to_notes")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            trigger_sql = _notes_trigger_sql(connection)
            assert trigger_sql is not None
            assert hashlib.sha256(trigger_sql.encode("utf-8")).hexdigest() == (
                NOTES_VERSION_BUMP_TRIGGER_SHA256
            )
    finally:
        engine.dispose()

    runtime_engine = create_engine(database_url)
    monkeypatch.setattr(
        "core.admin_repo.get_session",
        lambda: Session(runtime_engine),
    )
    try:
        NotesRepo().touch(note_ids[0])
        with runtime_engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT id, content, version, updated_at FROM notes "
                    "WHERE tenant_id=9706 ORDER BY id"
                )
            ).all()
        assert rows[0][0:3] == (note_ids[0], "target", 1)
        assert rows[0][3] != "2000-01-01 00:00:00"
        assert rows[1] == (
            note_ids[1],
            "other",
            0,
            "2000-01-01 00:00:00",
        )
    finally:
        runtime_engine.dispose()


def test_postgresql_notes_touch_is_scoped_and_versioned(monkeypatch):
    database_url = os.getenv("SEC_FINAL_06_NOTES_POSTGRES_URL")
    seed_database_url = os.getenv("SEC_FINAL_06_NOTES_MIGRATOR_URL")
    if not database_url or not seed_database_url:
        pytest.skip(
            "Set SEC_FINAL_06_NOTES_POSTGRES_URL and "
            "SEC_FINAL_06_NOTES_MIGRATOR_URL to a dedicated local 0059 test database"
        )

    url = make_url(database_url)
    seed_url = make_url(seed_database_url)
    urls = (url, seed_url)
    if any(
        not candidate.drivername.startswith("postgresql")
        or candidate.host not in {"127.0.0.1", "localhost", "::1"}
        or candidate.port is None
        or not (candidate.database or "").startswith("sec_pg_06_notes_")
        or {"host", "options"} & set(candidate.query)
        for candidate in urls
    ):
        pytest.fail("Notes PostgreSQL regression requires its dedicated local database")
    if (
        url.database != seed_url.database
        or url.host != seed_url.host
        or url.port != seed_url.port
        or not url.username
        or not seed_url.username
        or url.username == seed_url.username
    ):
        pytest.fail(
            "Notes PostgreSQL runtime and migrator URLs must use separate roles on one database"
        )

    with _without_libpq_destination_environment():
        runtime_engine = create_engine(database_url)
        seed_engine = create_engine(seed_database_url)
        tenant_ids: list[int] = []
        user_ids: list[int] = []
        site_ids: list[str] = []
        note_ids: list[int] = []
        try:
            with seed_engine.connect() as connection:
                assert connection.execute(
                    text(
                        "SELECT version_num FROM alembic_version"
                    )
                ).scalar_one() == "0059_normal_exclusions_scope"
            with runtime_engine.connect() as connection:
                role = connection.execute(
                    text(
                        "SELECT r.rolsuper, "
                        "pg_get_userbyid(d.datdba) = current_user, "
                        "has_schema_privilege(current_user, 'public', 'CREATE') "
                        "FROM pg_roles r "
                        "JOIN pg_database d ON d.datname=current_database() "
                        "WHERE r.rolname=current_user"
                    )
                ).one()
                assert role == (False, False, False)

            suffix = uuid.uuid4().hex
            with seed_engine.begin() as connection:
                for label in ("A", "B"):
                    tenant_ids.append(
                        connection.execute(
                            text(
                                "INSERT INTO tenants(name, active) "
                                "VALUES (:name, true) RETURNING id"
                            ),
                            {"name": f"SEC-FINAL-06 Notes {label} {suffix}"},
                        ).scalar_one()
                    )
                user_ids.append(
                    connection.execute(
                        text(
                            "INSERT INTO users "
                            "(tenant_id, email, password_hash, role, username, full_name) "
                            "VALUES (:tenant_id, :email, 'hash', 'admin', :username, :full_name) "
                            "RETURNING id"
                        ),
                        {
                            "tenant_id": tenant_ids[0],
                            "email": f"notes-a-{suffix}@example.test",
                            "username": f"notes-a-{suffix}",
                            "full_name": "Notes A",
                        },
                    ).scalar_one()
                )
                user_ids.append(
                    connection.execute(
                        text(
                            "INSERT INTO users "
                            "(tenant_id, email, password_hash, role, username, full_name) "
                            "VALUES (:tenant_id, :email, 'hash', 'admin', :username, :full_name) "
                            "RETURNING id"
                        ),
                        {
                            "tenant_id": tenant_ids[1],
                            "email": f"notes-b-{suffix}@example.test",
                            "username": f"notes-b-{suffix}",
                            "full_name": "Notes B",
                        },
                    ).scalar_one()
                )
                for index, tenant_id in enumerate(tenant_ids):
                    count = 2 if index == 0 else 1
                    for _ in range(count):
                        site_id = str(uuid.uuid4())
                        site_ids.append(site_id)
                        connection.execute(
                            text(
                                "INSERT INTO sites(id, name, tenant_id) "
                                "VALUES (:id, :name, :tenant_id)"
                            ),
                            {
                                "id": site_id,
                                "name": site_id,
                                "tenant_id": tenant_id,
                            },
                        )
                rows = (
                    (tenant_ids[0], user_ids[0], site_ids[0], "target"),
                    (tenant_ids[0], user_ids[0], site_ids[1], "same tenant other site"),
                    (tenant_ids[1], user_ids[1], site_ids[2], "other tenant"),
                )
                for tenant_id, user_id, site_id, content in rows:
                    note_ids.append(
                        connection.execute(
                            text(
                                "INSERT INTO notes "
                                "(tenant_id, user_id, site_id, content, updated_at, version) "
                                "VALUES (:tenant_id, :user_id, :site_id, :content, "
                                "TIMESTAMP '2000-01-01 00:00:00', 0) RETURNING id"
                            ),
                            {
                                "tenant_id": tenant_id,
                                "user_id": user_id,
                                "site_id": site_id,
                                "content": content,
                            },
                        ).scalar_one()
                    )

            monkeypatch.setattr(
                "core.admin_repo.get_session",
                lambda: Session(runtime_engine),
            )
            repo = NotesRepo()
            repo.touch(note_ids[0])
            with runtime_engine.connect() as connection:
                after_unconditional = connection.execute(
                    text(
                        "SELECT id, content, version, updated_at FROM notes "
                        "WHERE id IN (:target, :site_other, :tenant_other) ORDER BY id"
                    ),
                    {
                        "target": note_ids[0],
                        "site_other": note_ids[1],
                        "tenant_other": note_ids[2],
                    },
                ).all()
            assert [row[2] for row in after_unconditional] == [1, 0, 0]
            assert [row[1] for row in after_unconditional] == [
                "target",
                "same tenant other site",
                "other tenant",
            ]
            assert after_unconditional[0][3].year > 2000
            assert after_unconditional[1][3].year == 2000
            assert after_unconditional[2][3].year == 2000

            repo.touch(note_ids[0], expected_version=1)
            with pytest.raises(ConcurrencyError, match="stale version"):
                repo.touch(note_ids[0], expected_version=1)

            with runtime_engine.connect() as connection:
                final_rows = connection.execute(
                    text(
                        "SELECT id, content, version, updated_at FROM notes "
                        "WHERE id IN (:target, :site_other, :tenant_other) ORDER BY id"
                    ),
                    {
                        "target": note_ids[0],
                        "site_other": note_ids[1],
                        "tenant_other": note_ids[2],
                    },
                ).all()
            assert [row[2] for row in final_rows] == [2, 0, 0]
            assert [row[1] for row in final_rows] == [
                "target",
                "same tenant other site",
                "other tenant",
            ]
            assert final_rows[1:] == after_unconditional[1:]
        finally:
            if note_ids or user_ids or site_ids or tenant_ids:
                with seed_engine.begin() as connection:
                    if note_ids:
                        connection.execute(
                            text("DELETE FROM notes WHERE id = ANY(:ids)"),
                            {"ids": note_ids},
                        )
                    if user_ids:
                        connection.execute(
                            text("DELETE FROM users WHERE id = ANY(:ids)"),
                            {"ids": user_ids},
                        )
                    if site_ids:
                        connection.execute(
                            text("DELETE FROM sites WHERE id = ANY(:ids)"),
                            {"ids": site_ids},
                        )
                    if tenant_ids:
                        connection.execute(
                            text("DELETE FROM tenants WHERE id = ANY(:ids)"),
                            {"ids": tenant_ids},
                        )
            seed_engine.dispose()
            runtime_engine.dispose()


def test_unexpected_notes_trigger_rolls_back_0052(tmp_path, monkeypatch):
    target = tmp_path / "notes-unexpected-trigger.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _config(target)
    command.upgrade(config, "0051_add_site_scoped_menu_uniqueness")

    unexpected_sql = (
        "CREATE TRIGGER notes_version_bump_trg AFTER UPDATE ON notes "
        "BEGIN SELECT 1; END"
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"DROP TRIGGER IF EXISTS {NOTES_VERSION_BUMP_TRIGGER_NAME}"
            )
            connection.execute(
                text("INSERT INTO tenants(id, name, active) VALUES (9704, 'Unexpected Tenant', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO users(id, tenant_id, email, password_hash, role) "
                    "VALUES (9704, 9704, 'unexpected@example.test', 'hash', 'admin')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO notes(tenant_id, user_id, content, private_flag) "
                    "VALUES (9704, 9704, 'unchanged', 0)"
                )
            )
            connection.exec_driver_sql(unexpected_sql)
            before = _notes_row(connection)
    finally:
        engine.dispose()

    try:
        command.upgrade(config, "0052_add_site_id_to_notes")
    except RuntimeError as exc:
        assert "unexpected notes trigger" in str(exc)
    else:
        raise AssertionError("unexpected SQLite notes trigger was accepted")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "0051_add_site_scoped_menu_uniqueness"
            assert "site_id" not in {
                column["name"] for column in inspect(connection).get_columns("notes")
            }
            assert _notes_trigger_sql(connection) == unexpected_sql
            assert _notes_row(connection) == before
    finally:
        engine.dispose()
