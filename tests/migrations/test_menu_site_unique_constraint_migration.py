from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from core.models import Base, Menu


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DB = ROOT / "instance" / "yuplan_mvp.db"
REVISION = "0051_add_site_scoped_menu_uniqueness"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
    return connection


def _copy_source_database(target: Path) -> str:
    before_hash = _sha256(SOURCE_DB)
    source = _read_only_connection(SOURCE_DB)
    try:
        destination = sqlite3.connect(str(target))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()
    assert _sha256(SOURCE_DB) == before_hash
    return before_hash


def _alembic_config(target: Path) -> Config:
    assert ROOT not in target.parents
    assert "instance" not in target.parts
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{target}")
    return config


def _menu_schema(connection) -> tuple[list[tuple], list[tuple], list[tuple]]:
    return (
        connection.execute(text("PRAGMA table_info(menus)")).fetchall(),
        connection.execute(text("PRAGMA index_list(menus)")).fetchall(),
        connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='menus'"
            )
        ).fetchall(),
    )


def _menu_counts(connection) -> dict[str, int]:
    counts = {}
    for table in (
        "menus",
        "menu_variants",
        "commun_builder_menu_links",
        "commun_builder_publication_pins",
        "commun_builder_publication_revisions",
    ):
        counts[table] = connection.execute(
            text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one()
    return counts


def _upgrade_copy(target: Path, monkeypatch) -> str:
    source_hash = _copy_source_database(target)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    command.upgrade(_alembic_config(target), REVISION)
    return source_hash


def test_model_declares_site_scoped_menu_identity():
    constraints = {
        tuple(constraint.columns.keys())
        for constraint in Menu.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("tenant_id", "site_id", "year", "week") in constraints


def test_model_create_all_declares_site_scoped_menu_identity():
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with engine.connect() as connection:
            constraints = connection.execute(
                text("PRAGMA index_list(menus)")
            ).fetchall()
            unique_indexes = []
            for index in constraints:
                if index[2]:
                    unique_indexes.append(
                        tuple(
                            row[2]
                            for row in connection.execute(
                                text(f'PRAGMA index_info("{index[1]}")')
                            )
                        )
                    )
            assert ("tenant_id", "site_id", "year", "week") in unique_indexes
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_pilot_copy_migrates_without_touching_original(tmp_path, monkeypatch):
    target = tmp_path / "pilot-copy.db"
    source_hash = _upgrade_copy(target, monkeypatch)

    assert _sha256(SOURCE_DB) == source_hash
    source = _read_only_connection(SOURCE_DB)
    try:
        assert source.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        source.close()

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            table_info, indexes, table_sql = _menu_schema(connection)
            assert connection.execute(
                text("PRAGMA integrity_check")
            ).scalar_one() == "ok"
            assert connection.execute(
                text("PRAGMA foreign_key_check")
            ).fetchall() == []
            assert any(
                "uq_menu_tenant_site_year_week" in str(row)
                for row in table_sql
            )
            assert not any(
                "uq_menu_tenant_year_week" in str(row)
                for row in table_sql
            )
            assert any(row[1] == "ix_menus_tenant_site_week" for row in indexes)
            assert len(table_info) == 7
            assert _menu_counts(connection) == {
                "menus": 23,
                "menu_variants": 520,
                "commun_builder_menu_links": 22,
                "commun_builder_publication_pins": 8,
                "commun_builder_publication_revisions": 13,
            }
    finally:
        engine.dispose()


def test_historical_sites_without_tenant_id_are_repaired_deterministically(
    tmp_path, monkeypatch
):
    target = tmp_path / "historical-copy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _alembic_config(target)
    command.upgrade(config, "0050_add_password_reset_storage")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            assert "tenant_id" not in {
                column["name"] for column in inspect(engine).get_columns("sites")
            }
            connection.execute(
                text("INSERT INTO tenants(id, name, active) VALUES (9501, 'Historical', 1)")
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name) VALUES ('historical-site', 'Historical Site')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO menus(tenant_id, site_id, week, year, status) "
                    "VALUES (9501, 'historical-site', 20, 2034, 'draft')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, REVISION)
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT tenant_id FROM sites WHERE id='historical-site'")
            ).scalar_one() == 9501
            assert connection.execute(
                text(
                    "SELECT tenant_id, site_id, week, year FROM menus "
                    "WHERE site_id='historical-site'"
                )
            ).one() == (9501, "historical-site", 20, 2034)
    finally:
        engine.dispose()


def test_historical_ambiguous_menu_site_relation_fails_closed(tmp_path, monkeypatch):
    target = tmp_path / "ambiguous-copy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    config = _alembic_config(target)
    command.upgrade(config, "0050_add_password_reset_storage")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tenants(id, name, active) VALUES "
                    "(9502, 'Historical A', 1), (9503, 'Historical B', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name) VALUES ('ambiguous-site', 'Ambiguous Site')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO menus(tenant_id, site_id, week, year, status) VALUES "
                    "(9502, 'ambiguous-site', 21, 2034, 'draft'), "
                    "(9503, 'ambiguous-site', 22, 2034, 'draft')"
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="invalid menu tenant/site"):
        command.upgrade(config, REVISION)


def test_migrated_schema_allows_two_sites_and_rejects_exact_duplicate(
    tmp_path, monkeypatch
):
    target = tmp_path / "multi-site-copy.db"
    _upgrade_copy(target, monkeypatch)
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tenants(id, name, active) "
                    "VALUES (9401, '04J tenant', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id, version) VALUES "
                    "('04j-site-a', '04J A', 9401, 0), "
                    "('04j-site-b', '04J B', 9401, 0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO menus(tenant_id, site_id, week, year, status) "
                    "VALUES (9401, '04j-site-a', 18, 2034, 'draft'), "
                    "(9401, '04j-site-b', 18, 2034, 'draft')"
                )
            )
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO menus(tenant_id, site_id, week, year, status) "
                        "VALUES (9401, '04j-site-a', 18, 2034, 'draft')"
                    )
                )
    finally:
        engine.dispose()


def test_downgrade_stops_after_multi_site_data(tmp_path, monkeypatch):
    target = tmp_path / "downgrade-copy.db"
    _upgrade_copy(target, monkeypatch)
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO tenants(id, name, active) "
                    "VALUES (9402, '04J downgrade tenant', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO sites(id, name, tenant_id, version) VALUES "
                    "('04j-down-a', '04J down A', 9402, 0), "
                    "('04j-down-b', '04J down B', 9402, 0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO menus(tenant_id, site_id, week, year, status) "
                    "VALUES (9402, '04j-down-a', 19, 2034, 'draft'), "
                    "(9402, '04j-down-b', 19, 2034, 'draft')"
                )
            )
    finally:
        engine.dispose()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    with pytest.raises(RuntimeError, match="tenant/year/week collisions"):
        command.downgrade(_alembic_config(target), "0050_add_password_reset_storage")


def test_downgrade_succeeds_without_multi_site_collisions(tmp_path, monkeypatch):
    target = tmp_path / "downgrade-safe-copy.db"
    _upgrade_copy(target, monkeypatch)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target}")
    command.downgrade(_alembic_config(target), "0050_add_password_reset_storage")

    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            table_sql = connection.execute(
                text(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='table' AND name='menus'"
                )
            ).scalar_one()
            assert "uq_menu_tenant_year_week" in table_sql
            assert "uq_menu_tenant_site_year_week" not in table_sql
            assert connection.execute(
                text("PRAGMA integrity_check")
            ).scalar_one() == "ok"
            assert connection.execute(
                text("PRAGMA foreign_key_check")
            ).fetchall() == []
    finally:
        engine.dispose()
