from __future__ import annotations

import hashlib
import importlib
import json
import os

import pytest
from alembic import command
from sqlalchemy import Integer, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine

from tests.migrations.test_users_updated_at_migration import (
    _assert_postgresql_database,
    _config,
    _without_libpq_destination_environment,
)


REVISION = "0059_normal_exclusions_scope"
PREVIOUS = "0057_meal_registrations_schema"
migration = importlib.import_module("migrations.versions.0058_canonical_diet_identity")


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / "diet.db"
    url = f"sqlite:///{path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("YUPLAN_DIET_0058_MANIFEST", raising=False)
    cfg = _config(url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(url)
    try:
        yield cfg, engine, tmp_path, monkeypatch
    finally:
        engine.dispose()


def _seed(engine):
    with engine.begin() as conn:
        active = "TRUE" if conn.dialect.name == "postgresql" else "1"
        conn.execute(text(f"INSERT INTO tenants(id,name,active) VALUES (9,'Synthetic tenant',{active})"))
        conn.execute(text("INSERT INTO sites(id,name,tenant_id) VALUES ('site-a','Synthetic A',9)"))
        conn.execute(text(
            "INSERT INTO departments(id,site_id,name,resident_count_mode) "
            "VALUES ('dept-a','site-a','Synthetic department','fixed')"
        ))
        conn.execute(text("INSERT INTO diet_types(id,name) VALUES ('7','Synthetic legacy')"))
        conn.execute(text(
            "INSERT INTO dietary_types(id,tenant_id,site_id,name,requirement_key,semantics) "
            "VALUES (7,9,'site-a','Synthetic canonical','req_7','atomic'),"
            "(11,9,'site-a','Synthetic mapped','req_11','atomic')"
        ))
        conn.execute(text(
            "INSERT INTO department_diet_defaults(department_id,diet_type_id,default_count) "
            "VALUES ('dept-a','7',3)"
        ))
        conn.execute(text(
            "INSERT INTO department_diet_overrides(department_id,diet_type_id,day,meal,count) "
            "VALUES ('dept-a','7',1,'lunch',4)"
        ))
        conn.execute(text(
            "INSERT INTO weekview_registrations"
            "(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES "
            "(9,'dept-a',2030,1,1,'lunch','7',1),"
            "(9,'dept-a',2030,1,2,'lunch','7',1)"
        ))
        conn.execute(text(
            "CREATE TABLE normal_exclusions(tenant_id TEXT NOT NULL,site_id TEXT NOT NULL,"
            "year INTEGER NOT NULL,week INTEGER NOT NULL,day_index INTEGER NOT NULL,"
            "meal TEXT NOT NULL,alt TEXT NOT NULL,diet_type_id TEXT NOT NULL,"
            "UNIQUE(tenant_id,site_id,year,week,day_index,meal,alt,diet_type_id))"
        ))
        conn.execute(text(
            "INSERT INTO normal_exclusions VALUES ('9','site-a',2030,1,0,'lunch','1','7')"
        ))
        conn.execute(text(
            "CREATE TABLE diet_registrations(site_id TEXT,department_id TEXT,date TEXT,"
            "meal TEXT,diet_type_id TEXT,count INTEGER)"
        ))
        conn.execute(text(
            "INSERT INTO diet_registrations VALUES "
            "('site-a','dept-a','2030-01-01','lunch','7',5),"
            "('site-a','dept-a','2030-01-02','lunch','7',6)"
        ))
        if conn.dialect.name == "sqlite":
            conn.execute(text(
                "CREATE TRIGGER test_diet_default_trigger AFTER UPDATE ON department_diet_defaults "
                "BEGIN SELECT 1; END"
            ))


def _manifest(engine, path, monkeypatch):
    with engine.connect() as conn:
        _, rows = migration._source_rows(conn)
        classifications = []
        for name in migration.DIET_COLUMNS:
            for row in rows[name] or []:
                kind = "canonical" if (
                    name == "department_diet_overrides"
                    or (name == "weekview_registrations" and row["day_of_week"] == 2)
                    or (name == "diet_registrations" and row["date"] == "2030-01-02")
                ) else "legacy"
                classifications.append({
                    "table": name,
                    "row_hash": migration.source_row_hash(row),
                    "kind": kind,
                    "tenant_id": 9,
                    "site_id": "site-a",
                    "canonical_id": 7 if kind == "canonical" else 11,
                    "evidence": "Reviewed synthetic fixture provenance",
                })
        manifest = {"snapshots": migration.source_snapshots(conn), "rows": classifications}
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("YUPLAN_DIET_0058_MANIFEST", str(path))
    return manifest


def test_empty_migration_and_repeated_upgrade(database):
    cfg, engine, _, _ = database
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
        for name in ("department_diet_defaults", "department_diet_overrides"):
            assert isinstance(
                next(col["type"] for col in inspect(conn).get_columns(name) if col["name"] == "diet_type_id"),
                Integer,
            )
            assert any(
                fk["constrained_columns"] == ["diet_type_id"] and fk["referred_table"] == "dietary_types"
                for fk in inspect(conn).get_foreign_keys(name)
            )
        assert isinstance(
            next(
                column["type"] for column in inspect(conn).get_columns("normal_exclusions")
                if column["name"] == "diet_type_id"
            ),
            Integer,
        )
        exclusion_fks = inspect(conn).get_foreign_keys("normal_exclusions")
        assert any(fk["referred_table"] == "sites" for fk in exclusion_fks)
        assert any(fk["referred_table"] == "dietary_types" for fk in exclusion_fks)


def test_explicit_mixed_identity_preserves_data_and_triggers(database):
    cfg, engine, tmp_path, monkeypatch = database
    _seed(engine)
    _manifest(engine, tmp_path / "manifest.json", monkeypatch)
    with engine.connect() as conn:
        default_metadata = conn.execute(text(
            "SELECT default_count,created_at,updated_at,version FROM department_diet_defaults"
        )).one()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT diet_type_id,default_count,created_at,updated_at,version FROM department_diet_defaults"
        )).one() == (11, *default_metadata)
        assert conn.execute(text(
            "SELECT diet_type_id,count FROM department_diet_overrides"
        )).one() == (7, 4)
        assert conn.execute(text(
            "SELECT day_of_week,diet_type FROM weekview_registrations ORDER BY day_of_week"
        )).all() == [(1, "11"), (2, "7")]
        assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == 11
        assert conn.execute(text(
            "SELECT date,diet_type_id,count FROM diet_registrations ORDER BY date"
        )).all() == [("2030-01-01", "11", 5), ("2030-01-02", "7", 6)]
        assert conn.execute(text("SELECT count(*) FROM dietary_identity_0058_audit")).scalar_one() == 7
        assert conn.execute(text(
            "SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name='test_diet_default_trigger'"
        )).scalar_one() == 1
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []


@pytest.mark.parametrize(
    ("table", "selector_column", "selector_value"),
    [
        ("normal_exclusions", "alt", "1"),
        ("weekview_registrations", "day_of_week", 2),
        ("diet_registrations", "date", "2030-01-02"),
    ],
)
def test_unrelated_numeric_diet_identity_fails_closed(database, table, selector_column, selector_value):
    cfg, engine, tmp_path, monkeypatch = database
    _seed(engine)
    path = tmp_path / "manifest.json"
    manifest = _manifest(engine, path, monkeypatch)
    with engine.connect() as conn:
        source_rows = migration._source_rows(conn)[1][table]
    source = next(row for row in source_rows if str(row[selector_column]) == str(selector_value))
    row_hash = migration.source_row_hash(source)
    item = next(row for row in manifest["rows"] if row["table"] == table and row["row_hash"] == row_hash)
    item["kind"] = "unrelated"
    item["canonical_id"] = None
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="0058.*provenance|0059.*provenance"):
        command.upgrade(cfg, "head")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
        assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == "7"
        assert conn.execute(text(
            "SELECT day_of_week,diet_type FROM weekview_registrations ORDER BY day_of_week"
        )).all() == [(1, "7"), (2, "7")]
        assert conn.execute(text(
            "SELECT date,diet_type_id,count FROM diet_registrations ORDER BY date"
        )).all() == [("2030-01-01", "7", 5), ("2030-01-02", "7", 6)]
        assert "dietary_identity_0058_audit" not in inspect(conn).get_table_names()


@pytest.mark.parametrize(
    ("table", "selector_column", "selector_value"),
    [
        ("normal_exclusions", "alt", "1"),
        ("weekview_registrations", "day_of_week", 2),
        ("diet_registrations", "date", "2030-01-02"),
    ],
)
def test_missing_direct_reference_provenance_fails_closed(
    database, table, selector_column, selector_value
):
    cfg, engine, tmp_path, monkeypatch = database
    _seed(engine)
    path = tmp_path / "manifest.json"
    manifest = _manifest(engine, path, monkeypatch)
    with engine.connect() as conn:
        source_rows = migration._source_rows(conn)[1][table]
    source = next(row for row in source_rows if str(row[selector_column]) == str(selector_value))
    row_hash = migration.source_row_hash(source)
    manifest["rows"] = [
        row for row in manifest["rows"]
        if not (row["table"] == table and row["row_hash"] == row_hash)
    ]
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match=f"Missing 0058 row classification in {table}"):
        command.upgrade(cfg, "head")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
        assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == "7"
        assert conn.execute(text(
            "SELECT day_of_week,diet_type FROM weekview_registrations ORDER BY day_of_week"
        )).all() == [(1, "7"), (2, "7")]
        assert conn.execute(text(
            "SELECT date,diet_type_id,count FROM diet_registrations ORDER BY date"
        )).all() == [("2030-01-01", "7", 5), ("2030-01-02", "7", 6)]
        assert "dietary_identity_0058_audit" not in inspect(conn).get_table_names()


@pytest.mark.parametrize(
    ("table", "selector_column", "selector_value", "column"),
    [
        ("weekview_registrations", "day_of_week", 2, "diet_type"),
        ("diet_registrations", "date", "2030-01-02", "diet_type_id"),
    ],
)
def test_unrelated_text_diet_reference_fails_closed(
    database, table, selector_column, selector_value, column
):
    cfg, engine, tmp_path, monkeypatch = database
    _seed(engine)
    with engine.begin() as conn:
        where_column = "day_of_week" if selector_column == "day_of_week" else selector_column
        conn.execute(text(f"UPDATE {table} SET {column}='legacy-freeform' WHERE {where_column}=:value"), {
            "value": selector_value,
        })
    path = tmp_path / "manifest.json"
    manifest = _manifest(engine, path, monkeypatch)
    with engine.connect() as conn:
        source_rows = migration._source_rows(conn)[1][table]
    source = next(row for row in source_rows if str(row[selector_column]) == str(selector_value))
    row_hash = migration.source_row_hash(source)
    item = next(row for row in manifest["rows"] if row["table"] == table and row["row_hash"] == row_hash)
    item["kind"] = "unrelated"
    item["canonical_id"] = None
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match=f"0058 unrelated dietary reference lacks canonical provenance in {table}"):
        command.upgrade(cfg, "head")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
        assert conn.execute(text(
            f"SELECT {column} FROM {table} WHERE {selector_column}=:value"
        ), {"value": selector_value}).scalar_one() == "legacy-freeform"
        assert "dietary_identity_0058_audit" not in inspect(conn).get_table_names()


@pytest.mark.parametrize(
    "provenance_error",
    ["missing", "unrelated", "contradictory", "wrong_scope", "ambiguous"],
)
def test_0059_rejects_invalid_normal_exclusion_provenance(database, provenance_error):
    cfg, engine, tmp_path, monkeypatch = database
    _seed(engine)
    _manifest(engine, tmp_path / "manifest.json", monkeypatch)
    command.upgrade(cfg, "0058_canonical_diet_identity")
    if provenance_error == "missing":
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM dietary_identity_0058_audit WHERE table_name='normal_exclusions'"
            ))
    elif provenance_error == "unrelated":
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE dietary_identity_0058_audit "
                "SET kind='unrelated',canonical_id=NULL WHERE table_name='normal_exclusions'"
            ))
    elif provenance_error == "contradictory":
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE dietary_identity_0058_audit SET source_id='8' "
                "WHERE table_name='normal_exclusions'"
            ))
    elif provenance_error == "wrong_scope":
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE dietary_identity_0058_audit SET site_id='site-b' "
                "WHERE table_name='normal_exclusions'"
            ))
    else:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO diet_types(id,name) VALUES ('007','Ambiguous legacy ID')"))
            audit = conn.execute(text(
                "SELECT source_key FROM dietary_identity_0058_audit "
                "WHERE table_name='normal_exclusions'"
            )).scalar_one()
            source_key = json.loads(audit)
            source_key["diet_type_id"] = "007"
            source_key_json = migration._json(source_key)
            conn.execute(text(
                "INSERT INTO dietary_identity_0058_audit"
                "(table_name,source_row_hash,source_key,source_id,kind,tenant_id,site_id,"
                "canonical_id,evidence,manifest_hash) "
                "VALUES ('normal_exclusions',:row_hash,:source_key,'007','legacy',9,'site-a',"
                "11,'Ambiguous synthetic provenance',:manifest_hash)"
            ), {
                "row_hash": hashlib.sha256(source_key_json.encode("utf-8")).hexdigest(),
                "source_key": source_key_json,
                "manifest_hash": "0" * 64,
            })

    with pytest.raises(RuntimeError, match="0059.*(provenance|identity|scope)"):
        command.upgrade(cfg, "head")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0058_canonical_diet_identity"
        assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == "11"
        assert "normal_exclusions" in inspect(conn).get_table_names()
        assert "_normal_exclusions_0059_new" not in inspect(conn).get_table_names()


def test_weekview_reserved_normal_keys_are_preserved(database):
    cfg, engine, tmp_path, monkeypatch = database
    _seed(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO weekview_registrations"
            "(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) VALUES "
            "(9,'dept-a',2030,1,3,'lunch','normal',1),"
            "(9,'dept-a',2030,1,4,'lunch','normalkost',1)"
        ))
    path = tmp_path / "manifest.json"
    manifest = _manifest(engine, path, monkeypatch)
    with engine.connect() as conn:
        reserved_hashes = {
            migration.source_row_hash(source)
            for source in migration._source_rows(conn)[1]["weekview_registrations"]
            if str(source["diet_type"]).casefold() in {"normal", "normalkost"}
        }
    manifest["rows"] = [
        row for row in manifest["rows"]
        if not (
            row["table"] == "weekview_registrations"
                and row["row_hash"] in reserved_hashes
        )
    ]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT day_of_week,diet_type FROM weekview_registrations "
            "WHERE day_of_week IN (3,4) ORDER BY day_of_week"
        )).all() == [(3, "normal"), (4, "normalkost")]


def test_preexisting_canonical_row_without_legacy_identity(database):
    cfg, engine, tmp_path, monkeypatch = database
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tenants(id,name,active) VALUES (9,'Synthetic tenant',1)"))
        conn.execute(text("INSERT INTO sites(id,name,tenant_id) VALUES ('site-a','Synthetic A',9)"))
        conn.execute(text(
            "INSERT INTO departments(id,site_id,name,resident_count_mode) "
            "VALUES ('dept-a','site-a','Synthetic department','fixed')"
        ))
        conn.execute(text(
            "INSERT INTO dietary_types(id,tenant_id,site_id,name,requirement_key,semantics) "
            "VALUES (7,9,'site-a','Synthetic canonical','req_7','atomic')"
        ))
        conn.execute(text(
            "INSERT INTO department_diet_defaults(department_id,diet_type_id,default_count) "
            "VALUES ('dept-a','7',2)"
        ))
        _, rows = migration._source_rows(conn)
        item = rows["department_diet_defaults"][0]
        manifest = {
            "snapshots": migration.source_snapshots(conn),
            "rows": [{
                "table": "department_diet_defaults",
                "row_hash": migration.source_row_hash(item),
                "kind": "canonical",
                "tenant_id": 9,
                "site_id": "site-a",
                "canonical_id": 7,
                "evidence": "Reviewed synthetic canonical provenance",
            }],
        }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("YUPLAN_DIET_0058_MANIFEST", str(path))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT diet_type_id,default_count FROM department_diet_defaults"
        )).one() == (7, 2)


def test_canonical_weekview_row_without_defaults_requires_classification(database):
    cfg, engine, tmp_path, monkeypatch = database
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tenants(id,name,active) VALUES (9,'Synthetic tenant',1)"))
        conn.execute(text("INSERT INTO sites(id,name,tenant_id) VALUES ('site-a','Synthetic A',9)"))
        conn.execute(text(
            "INSERT INTO departments(id,site_id,name,resident_count_mode) "
            "VALUES ('dept-a','site-a','Synthetic department','fixed')"
        ))
        conn.execute(text(
            "INSERT INTO dietary_types(id,tenant_id,site_id,name,requirement_key,semantics) "
            "VALUES (7,9,'site-a','Synthetic canonical','req_7','atomic')"
        ))
        conn.execute(text(
            "INSERT INTO weekview_registrations"
            "(tenant_id,department_id,year,week,day_of_week,meal,diet_type,marked) "
            "VALUES (9,'dept-a',2030,1,1,'lunch','7',1)"
        ))
        manifest = {"snapshots": migration.source_snapshots(conn), "rows": []}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("YUPLAN_DIET_0058_MANIFEST", str(path))
    with pytest.raises(RuntimeError, match="Missing 0058 row classification"):
        command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
        assert conn.execute(text("SELECT diet_type FROM weekview_registrations")).scalar_one() == "7"


def test_sqlite_scope_guards_work_even_with_foreign_keys_disabled(database):
    cfg, engine, _, _ = database
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 0
        conn.execute(text("INSERT INTO tenants(id,name,active) VALUES (9,'Tenant A',1),(10,'Tenant B',1)"))
        conn.execute(text(
            "INSERT INTO sites(id,name,tenant_id) VALUES ('site-a','Site A',9),('site-b','Site B',10)"
        ))
        conn.execute(text(
            "INSERT INTO departments(id,site_id,name,resident_count_mode) "
            "VALUES ('dept-a','site-a','Department A','fixed')"
        ))
        conn.execute(text(
            "INSERT INTO dietary_types(id,tenant_id,site_id,name) "
            "VALUES (7,9,'site-a','Own'),(8,10,'site-b','Other')"
        ))
        conn.execute(text(
            "INSERT INTO department_diet_defaults(department_id,diet_type_id,default_count) "
            "VALUES ('dept-a',7,2)"
        ))
    for sql in (
        "INSERT INTO department_diet_overrides VALUES ('dept-a',8,1,'lunch',2,NULL)",
        "INSERT INTO department_diet_defaults(department_id,diet_type_id) VALUES ('dept-a',999)",
        "DELETE FROM dietary_types WHERE id=7",
        "UPDATE dietary_types SET site_id='site-b' WHERE id=7",
        "UPDATE departments SET site_id='site-b' WHERE id='dept-a'",
        "UPDATE sites SET tenant_id=10 WHERE id='site-a'",
    ):
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text(sql))
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT diet_type_id,default_count FROM department_diet_defaults"
        )).one() == (7, 2)


def test_postgresql_explicit_migration_and_rollback(tmp_path, monkeypatch):
    url = os.getenv("SEC_PG_DIET_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SEC_PG_DIET_TEST_DATABASE_URL to an empty isolated PostgreSQL database")
    with _without_libpq_destination_environment():
        _assert_postgresql_database(url, require_empty=True)
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.delenv("YUPLAN_DIET_0058_MANIFEST", raising=False)
        cfg = _config(url)
        engine = create_engine(url)
        try:
            command.upgrade(cfg, PREVIOUS)
            _seed(engine)
            path = tmp_path / "manifest.json"
            manifest = _manifest(engine, path, monkeypatch)
            exclusion_item = next(
                item for item in manifest["rows"] if item["table"] == "normal_exclusions"
            )
            for table in ("normal_exclusions", "weekview_registrations", "diet_registrations"):
                unrelated = json.loads(json.dumps(manifest))
                unrelated_item = next(
                    item for item in unrelated["rows"] if item["table"] == table
                )
                unrelated_item["kind"] = "unrelated"
                unrelated_item["canonical_id"] = None
                path.write_text(json.dumps(unrelated), encoding="utf-8")
                with pytest.raises(RuntimeError, match="0058.*provenance"):
                    command.upgrade(cfg, "head")
                with engine.connect() as conn:
                    assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
                    assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == "7"
                    assert conn.execute(text(
                        "SELECT day_of_week,diet_type FROM weekview_registrations ORDER BY day_of_week"
                    )).all() == [(1, "7"), (2, "7")]
                    assert conn.execute(text(
                        "SELECT date,diet_type_id,count FROM diet_registrations ORDER BY date"
                    )).all() == [("2030-01-01", "7", 5), ("2030-01-02", "7", 6)]
                    assert "dietary_identity_0058_audit" not in inspect(conn).get_table_names()

            path.write_text(json.dumps(manifest), encoding="utf-8")
            with pytest.raises(IntegrityError) as original:
                with engine.begin() as conn:
                    conn.execute(text(
                        "INSERT INTO department_diet_defaults(department_id,diet_type_id,default_count) "
                        "VALUES ('dept-a','11',2)"
                    ))
            assert original.value.orig.sqlstate == "23503"

            def inject(conn, _cursor, statement, _parameters, _context, _executemany):
                if conn.engine.url == engine.url and "CREATE TABLE dietary_identity_0058_audit" in statement:
                    raise RuntimeError("injected 0058 failure")

            event.listen(Engine, "before_cursor_execute", inject)
            try:
                with pytest.raises(RuntimeError, match="injected 0058 failure"):
                    command.upgrade(cfg, "head")
            finally:
                event.remove(Engine, "before_cursor_execute", inject)
            with engine.connect() as conn:
                assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
                assert conn.execute(text(
                    "SELECT diet_type_id,default_count FROM department_diet_defaults"
                )).one() == ("7", 3)
                assert "dietary_identity_0058_audit" not in inspect(conn).get_table_names()

            command.upgrade(cfg, "0058_canonical_diet_identity")
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE dietary_identity_0058_audit "
                    "SET kind='unrelated',canonical_id=NULL WHERE table_name='normal_exclusions'"
                ))
            with pytest.raises(RuntimeError, match="0059 requires explicit canonical provenance"):
                command.upgrade(cfg, "head")
            with engine.connect() as conn:
                assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0058_canonical_diet_identity"
                assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == "11"
                assert "_normal_exclusions_0059_new" not in inspect(conn).get_table_names()

            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE dietary_identity_0058_audit SET kind=:kind,canonical_id=:canonical_id "
                    "WHERE table_name='normal_exclusions' AND source_row_hash=:row_hash"
                ), {
                    "kind": exclusion_item["kind"],
                    "canonical_id": exclusion_item["canonical_id"],
                    "row_hash": exclusion_item["row_hash"],
                })
            command.upgrade(cfg, "head")
            command.upgrade(cfg, "head")
            with engine.connect() as conn:
                assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
                assert conn.execute(text(
                    "SELECT diet_type_id,default_count FROM department_diet_defaults"
                )).one() == (11, 3)
                assert conn.execute(text(
                    "SELECT day_of_week,diet_type FROM weekview_registrations ORDER BY day_of_week"
                )).all() == [(1, "11"), (2, "7")]
                assert conn.execute(text("SELECT diet_type_id FROM normal_exclusions")).scalar_one() == 11
                assert conn.execute(text(
                    "SELECT date,diet_type_id,count FROM diet_registrations ORDER BY date"
                )).all() == [("2030-01-01", "11", 5), ("2030-01-02", "7", 6)]
                assert conn.execute(text("SELECT count(*) FROM dietary_identity_0058_audit")).scalar_one() == 7
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE dietary_types SET site_id='wrong' WHERE id=11"))
        finally:
            engine.dispose()


@pytest.mark.parametrize("failure", ["missing", "stale", "scope", "collision", "injected"])
def test_invalid_manifest_or_failure_rolls_back(database, failure):
    cfg, engine, tmp_path, monkeypatch = database
    _seed(engine)
    path = tmp_path / "manifest.json"
    manifest = _manifest(engine, path, monkeypatch)
    if failure == "missing":
        manifest["rows"].pop()
    elif failure == "stale":
        manifest["snapshots"]["sites"] = "0" * 64
    elif failure == "scope":
        manifest["rows"][0]["site_id"] = "other-site"
    elif failure == "collision":
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO diet_types(id,name) VALUES ('11','Second synthetic legacy')"))
            conn.execute(text(
                "INSERT INTO department_diet_defaults(department_id,diet_type_id,default_count) "
                "VALUES ('dept-a','11',2)"
            ))
        manifest = _manifest(engine, path, monkeypatch)
    path.write_text(json.dumps(manifest), encoding="utf-8")

    def inject(conn, _cursor, statement, _parameters, _context, _executemany):
        if failure == "injected" and conn.engine.url == engine.url and "CREATE TABLE dietary_identity_0058_audit" in statement:
            raise RuntimeError("injected 0058 failure")

    event.listen(Engine, "before_cursor_execute", inject)
    try:
        with pytest.raises(RuntimeError):
            command.upgrade(cfg, "head")
    finally:
        event.remove(Engine, "before_cursor_execute", inject)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
        assert conn.execute(text(
            "SELECT diet_type_id,default_count FROM department_diet_defaults WHERE default_count=3"
        )).one() == ("7", 3)
        assert "dietary_identity_0058_audit" not in inspect(conn).get_table_names()
        assert any(
            fk["constrained_columns"] == ["diet_type_id"] and fk["referred_table"] == "diet_types"
            for fk in inspect(conn).get_foreign_keys("department_diet_defaults")
        )
