from __future__ import annotations

import importlib
import os

import pytest
from alembic import command
from sqlalchemy import Integer, create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from tests.migrations.test_users_updated_at_migration import (
    _assert_postgresql_database,
    _config,
    _without_libpq_destination_environment,
)


PREVIOUS = "0058_canonical_diet_identity"
HEAD = "0059_normal_exclusions_scope"
TEMP_TABLE = "_normal_exclusions_0059_new"
LEGACY_TABLE = """
CREATE TABLE normal_exclusions(
    tenant_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    day_index INTEGER NOT NULL,
    meal TEXT NOT NULL,
    alt TEXT NOT NULL,
    diet_type_id TEXT NOT NULL,
    UNIQUE(tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id)
)
"""
EXCLUSION_COLUMNS = (
    "tenant_id", "site_id", "year", "week", "day_index", "meal", "alt", "diet_type_id",
)
migration_0058 = importlib.import_module("migrations.versions.0058_canonical_diet_identity")


def _seed_parents(engine) -> None:
    with engine.begin() as conn:
        active = "TRUE" if conn.dialect.name == "postgresql" else "1"
        conn.execute(text(
            f"INSERT INTO tenants(id,name,active) VALUES "
            f"(9,'Synthetic tenant A',{active}),(10,'Synthetic tenant B',{active})"
        ))
        conn.execute(text(
            "INSERT INTO sites(id,name,tenant_id) VALUES "
            "('site-a','Synthetic A',9),('site-b','Synthetic B',9),('site-c','Synthetic C',10)"
        ))
        conn.execute(text(
            "INSERT INTO dietary_types(id,tenant_id,site_id,name,requirement_key,semantics) VALUES "
            "(7,9,'site-a','Canonical A','req_a','atomic'),"
            "(8,9,'site-b','Canonical B','req_b','atomic'),"
            "(9,10,'site-c','Canonical C','req_c','atomic')"
        ))


def _prepare(url: str, config, engine) -> None:
    command.upgrade(config, PREVIOUS)
    _seed_parents(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(LEGACY_TABLE)


def _record_canonical_provenance(engine) -> None:
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
            "FROM normal_exclusions"
        )).mappings().all()
        for row in rows:
            source = dict(row)
            source_key = migration_0058._json({
                column: migration_0058._encoded(source[column])
                for column in EXCLUSION_COLUMNS
            })
            conn.execute(text(
                "INSERT INTO dietary_identity_0058_audit"
                "(table_name,source_row_hash,source_key,source_id,kind,tenant_id,site_id,"
                "canonical_id,evidence,manifest_hash) "
                "VALUES ('normal_exclusions',:row_hash,:source_key,:source_id,'canonical',"
                ":tenant_id,:site_id,:canonical_id,'Explicit synthetic canonical provenance',:manifest_hash)"
            ), {
                "row_hash": migration_0058.source_row_hash(source),
                "source_key": source_key,
                "source_id": str(source["diet_type_id"]),
                "tenant_id": int(source["tenant_id"]),
                "site_id": str(source["site_id"]),
                "canonical_id": int(source["diet_type_id"]),
                "manifest_hash": "0" * 64,
            })


def _assert_canonical_schema(engine) -> None:
    with engine.connect() as conn:
        columns = {column["name"]: column["type"] for column in inspect(conn).get_columns("normal_exclusions")}
        assert isinstance(columns["tenant_id"], Integer)
        assert isinstance(columns["diet_type_id"], Integer)
        foreign_keys = inspect(conn).get_foreign_keys("normal_exclusions")
        assert any(
            fk["constrained_columns"] == ["tenant_id", "site_id"]
            and fk["referred_table"] == "sites"
            for fk in foreign_keys
        )
        assert any(
            fk["constrained_columns"] == ["tenant_id", "site_id", "diet_type_id"]
            and fk["referred_table"] == "dietary_types"
            for fk in foreign_keys
        )
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD


def test_normal_exclusions_scope_migration_sqlite(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'normal-exclusions.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)
    engine = create_engine(url)
    try:
        _prepare(url, config, engine)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO normal_exclusions VALUES "
                "('9','site-a',2030,1,0,'lunch','1','7')"
            ))
        _record_canonical_provenance(engine)

        command.upgrade(config, "head")
        _assert_canonical_schema(engine)
        with engine.connect() as conn:
            assert conn.execute(text(
                "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                "FROM normal_exclusions"
            )).one() == (9, "site-a", 2030, 1, 0, "lunch", "1", 7)
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            trigger_names = {
                row[0] for row in conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='trigger' "
                    "AND tbl_name IN ('normal_exclusions','dietary_types','sites')"
                ))
            }
            assert "trg_normal_exclusions_0059_insert_scope" in trigger_names

        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO normal_exclusions VALUES "
                    "(9,'site-a',2030,1,0,'lunch','1',8)"
                ))

        command.downgrade(config, PREVIOUS)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
            assert conn.execute(text(
                "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                "FROM normal_exclusions"
            )).one() == ("9", "site-a", 2030, 1, 0, "lunch", "1", "7")
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        _assert_canonical_schema(engine)
        with engine.connect() as conn:
            assert conn.execute(text(
                "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                "FROM normal_exclusions"
            )).one() == (9, "site-a", 2030, 1, 0, "lunch", "1", 7)
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([("9", "site-a", "999")], "outside canonical tenant/site scope"),
        ([("9", "site-a", "8")], "outside canonical tenant/site scope"),
        ([("9", "site-a", "9")], "outside canonical tenant/site scope"),
        ([("9", "site-a", "07")], "noncanonical dietary ID"),
        ([("09", "site-a", "7"), ("9", "site-a", "7")], "key collision"),
    ],
)
def test_invalid_normal_exclusion_fails_without_mutation(tmp_path, monkeypatch, rows, message):
    url = f"sqlite:///{(tmp_path / 'invalid.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)
    engine = create_engine(url)
    try:
        _prepare(url, config, engine)
        with engine.begin() as conn:
            for tenant_id, site_id, diet_id in rows:
                conn.execute(text(
                    "INSERT INTO normal_exclusions VALUES "
                    "(:tenant,:site,2030,1,0,'lunch','1',:diet)"
                ), {"tenant": tenant_id, "site": site_id, "diet": diet_id})
            before = conn.execute(text(
                "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                "FROM normal_exclusions ORDER BY tenant_id,diet_type_id"
            )).all()
        _record_canonical_provenance(engine)

        with pytest.raises(RuntimeError, match=message):
            command.upgrade(config, "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
            assert conn.execute(text(
                "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                "FROM normal_exclusions ORDER BY tenant_id,diet_type_id"
            )).all() == before
            assert "_normal_exclusions_0059_new" not in inspect(conn).get_table_names()
            assert "uq_sites_tenant_id_id" not in {
                index["name"] for index in inspect(conn).get_indexes("sites")
            }
    finally:
        engine.dispose()


def test_normal_exclusions_ddl_failure_rolls_back(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'rollback.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)
    engine = create_engine(url)
    try:
        _prepare(url, config, engine)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO normal_exclusions VALUES "
                "('9','site-a',2030,1,0,'lunch','1','7')"
            ))
        _record_canonical_provenance(engine)

        def inject(conn, _cursor, statement, _parameters, _context, _executemany):
            if conn.engine.url == engine.url and "RENAME TO normal_exclusions" in statement:
                raise RuntimeError("injected 0059 failure")

        event.listen(Engine, "before_cursor_execute", inject)
        try:
            with pytest.raises(RuntimeError, match="injected 0059 failure"):
                command.upgrade(config, "head")
        finally:
            event.remove(Engine, "before_cursor_execute", inject)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
            assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == "7"
            assert "_normal_exclusions_0059_new" not in inspect(conn).get_table_names()
            assert "uq_sites_tenant_id_id" not in {
                index["name"] for index in inspect(conn).get_indexes("sites")
            }
    finally:
        engine.dispose()


def test_normal_exclusions_scope_migration_postgresql(tmp_path, monkeypatch):
    url = os.getenv("SEC_PG_DIET_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SEC_PG_DIET_TEST_DATABASE_URL to an empty isolated PostgreSQL database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(url, require_empty=True)
        monkeypatch.setenv("DATABASE_URL", url)
        config = _config(url)
        engine = create_engine(url)
        try:
            _prepare(url, config, engine)
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO normal_exclusions VALUES "
                    "('9','site-a',2030,1,0,'lunch','1','7')"
                ))
            _record_canonical_provenance(engine)
            def inject(conn, _cursor, statement, _parameters, _context, _executemany):
                if conn.engine.url == engine.url and "RENAME TO normal_exclusions" in statement:
                    raise RuntimeError("injected 0059 PostgreSQL failure")

            event.listen(Engine, "before_cursor_execute", inject)
            try:
                with pytest.raises(RuntimeError, match="injected 0059 PostgreSQL failure"):
                    command.upgrade(config, "head")
            finally:
                event.remove(Engine, "before_cursor_execute", inject)
            with engine.connect() as conn:
                assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
                assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == "7"
                assert TEMP_TABLE not in inspect(conn).get_table_names()
                assert "uq_sites_tenant_id_id" not in {
                    index["name"] for index in inspect(conn).get_indexes("sites")
                }
            command.upgrade(config, "head")
            _assert_canonical_schema(engine)
            with engine.connect() as conn:
                assert conn.execute(text(
                    "SELECT tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id "
                    "FROM normal_exclusions"
                )).one() == (9, "site-a", 2030, 1, 0, "lunch", "1", 7)
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:
                    conn.execute(text(
                        "INSERT INTO normal_exclusions VALUES "
                        "(9,'site-a',2030,1,0,'lunch','1',8)"
                    ))
            command.upgrade(config, "head")
            _assert_canonical_schema(engine)
        finally:
            engine.dispose()
