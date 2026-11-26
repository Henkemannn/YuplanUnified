from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from core.weekview.schema import _metadata, ensure_weekview_schema, verify_weekview_schema


ROOT = Path(__file__).resolve().parents[2]
REVISION = "0055_weekview_schema"
EXPECTED_TABLES = {
    "weekview_registrations",
    "weekview_versions",
    "weekview_residents_count",
    "weekview_alt2_flags",
}


def _alembic_config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return config


def _run_alembic(db_path: Path, action, revision: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    try:
        action(_alembic_config(db_path), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _stamp_0054(db_path: Path) -> None:
    _run_alembic(db_path, command.stamp, "0054_add_menu_import_guards")


def _upgrade(db_path: Path) -> None:
    _run_alembic(db_path, command.upgrade, REVISION)


def _create_legacy_dependencies(conn) -> None:
    conn.exec_driver_sql(
        "CREATE TABLE sites (id TEXT PRIMARY KEY, tenant_id INTEGER NOT NULL)"
    )
    conn.exec_driver_sql(
        "CREATE TABLE departments (id TEXT PRIMARY KEY, site_id TEXT NOT NULL)"
    )
    conn.exec_driver_sql(
        "INSERT INTO sites(id, tenant_id) VALUES ('site-1', 7)"
    )
    conn.exec_driver_sql(
        "INSERT INTO departments(id, site_id) VALUES ('dep-1', 'site-1')"
    )


def _create_legacy_alt2(conn, *, unique: bool = True) -> None:
    suffix = ", UNIQUE(tenant_id, department_id, year, week, day_of_week)" if unique else ""
    conn.exec_driver_sql(
        f"""
        CREATE TABLE weekview_alt2_flags (
            tenant_id INTEGER NOT NULL,
            department_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            week INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            is_alt2 INTEGER NOT NULL
            {suffix}
        )
        """
    )


def test_fresh_migration_provisions_contract_and_unique_keys(tmp_path):
    db_path = tmp_path / "fresh.db"

    _stamp_0054(db_path)
    _upgrade(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        assert EXPECTED_TABLES.issubset(inspector.get_table_names())
        expected_unique = {
            "weekview_registrations": (
                "tenant_id",
                "department_id",
                "year",
                "week",
                "day_of_week",
                "meal",
                "diet_type",
            ),
            "weekview_versions": ("tenant_id", "department_id", "year", "week"),
            "weekview_residents_count": (
                "tenant_id",
                "department_id",
                "year",
                "week",
                "day_of_week",
                "meal",
            ),
            "weekview_alt2_flags": (
                "site_id",
                "department_id",
                "year",
                "week",
                "day_of_week",
            ),
        }
        for table_name, unique_key in expected_unique.items():
            uniques = {
                tuple(item["column_names"])
                for item in inspector.get_unique_constraints(table_name)
            }
            assert unique_key in uniques
            assert "updated_at" in {item["name"] for item in inspector.get_columns(table_name)}
    finally:
        engine.dispose()


def test_existing_canonical_data_and_menu_choices_survive_migration(tmp_path):
    db_path = tmp_path / "canonical.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_registrations (
                tenant_id TEXT NOT NULL, department_id TEXT NOT NULL,
                year INTEGER NOT NULL, week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL, meal TEXT NOT NULL,
                diet_type TEXT NOT NULL, marked INTEGER NOT NULL DEFAULT 0,
                UNIQUE(tenant_id, department_id, year, week, day_of_week, meal, diet_type)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_versions (
                tenant_id TEXT NOT NULL, department_id TEXT NOT NULL,
                year INTEGER NOT NULL, week INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                UNIQUE(tenant_id, department_id, year, week)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_residents_count (
                tenant_id TEXT NOT NULL, department_id TEXT NOT NULL,
                year INTEGER NOT NULL, week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL, meal TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(tenant_id, department_id, year, week, day_of_week, meal)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_alt2_flags (
                site_id TEXT NOT NULL, department_id TEXT NOT NULL,
                year INTEGER NOT NULL, week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 0,
                UNIQUE(site_id, department_id, year, week, day_of_week)
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO weekview_registrations VALUES ('7', 'dep-1', 2026, 6, 1, 'lunch', 'gluten', 1)"
        )
        conn.exec_driver_sql(
            "INSERT INTO weekview_versions VALUES ('7', 'dep-1', 2026, 6, 4)"
        )
        conn.exec_driver_sql(
            "INSERT INTO weekview_residents_count VALUES ('7', 'dep-1', 2026, 6, 1, 'lunch', 12)"
        )
        conn.exec_driver_sql(
            "INSERT INTO weekview_alt2_flags VALUES ('site-1', 'dep-1', 2026, 6, 1, 0)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE department_menu_choices (id INTEGER PRIMARY KEY, selected_variant TEXT)"
        )
        conn.exec_driver_sql("INSERT INTO department_menu_choices VALUES (1, 'alt2')")
    engine.dispose()

    _stamp_0054(db_path)
    _upgrade(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT marked FROM weekview_registrations")).scalar_one() == 1
            assert conn.execute(text("SELECT version FROM weekview_versions")).scalar_one() == 4
            assert conn.execute(text("SELECT count FROM weekview_residents_count")).scalar_one() == 12
            assert conn.execute(text("SELECT enabled FROM weekview_alt2_flags")).scalar_one() == 0
            assert conn.execute(text("SELECT selected_variant FROM department_menu_choices")).scalar_one() == "alt2"
    finally:
        engine.dispose()


def test_valid_legacy_alt2_transfers_all_values(tmp_path):
    db_path = tmp_path / "legacy-valid.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_legacy_dependencies(conn)
        _create_legacy_alt2(conn)
        conn.exec_driver_sql(
            "INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 1)"
        )
        conn.exec_driver_sql(
            "INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 2, 0)"
        )
    engine.dispose()

    _stamp_0054(db_path)
    _upgrade(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT site_id, department_id, year, week, day_of_week, enabled "
                    "FROM weekview_alt2_flags ORDER BY day_of_week"
                )
            ).all()
            assert [tuple(row) for row in rows] == [
                ("site-1", "dep-1", 2026, 6, 1, 1),
                ("site-1", "dep-1", 2026, 6, 2, 0),
            ]
            assert "weekview_alt2_flags_legacy_backup" not in inspect(conn).get_table_names()
    finally:
        engine.dispose()


@pytest.mark.parametrize("scenario", ("missing_department", "wrong_tenant", "duplicate"))
def test_invalid_legacy_alt2_aborts_without_data_loss(tmp_path, scenario):
    db_path = tmp_path / f"legacy-{scenario}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_legacy_dependencies(conn)
        _create_legacy_alt2(conn, unique=scenario != "duplicate")
        if scenario == "missing_department":
            conn.exec_driver_sql(
                "INSERT INTO weekview_alt2_flags VALUES (7, 'missing', 2026, 6, 1, 1)"
            )
        elif scenario == "wrong_tenant":
            conn.exec_driver_sql(
                "INSERT INTO weekview_alt2_flags VALUES (99, 'dep-1', 2026, 6, 1, 1)"
            )
        else:
            conn.exec_driver_sql(
                "INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 0)"
            )
    engine.dispose()

    _stamp_0054(db_path)
    original_rows = None
    original_columns = None
    with create_engine(f"sqlite:///{db_path}").connect() as conn:
        original_rows = conn.execute(
            text("SELECT tenant_id, department_id, year, week, day_of_week, is_alt2 FROM weekview_alt2_flags ORDER BY rowid")
        ).all()
        original_columns = [column["name"] for column in inspect(conn).get_columns("weekview_alt2_flags")]
    with pytest.raises(RuntimeError, match="legacy Alt2 migration aborted"):
        _upgrade(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert "weekview_alt2_flags" in inspect(conn).get_table_names()
            assert "weekview_alt2_flags_new" not in inspect(conn).get_table_names()
            expected_count = 2 if scenario == "duplicate" else 1
            assert conn.execute(text("SELECT COUNT(*) FROM weekview_alt2_flags")).scalar_one() == expected_count
            assert [column["name"] for column in inspect(conn).get_columns("weekview_alt2_flags")] == original_columns
            assert conn.execute(
                text("SELECT tenant_id, department_id, year, week, day_of_week, is_alt2 FROM weekview_alt2_flags ORDER BY rowid")
            ).all() == original_rows
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0054_add_menu_import_guards"
    finally:
        engine.dispose()


def test_bootstrap_is_explicit_and_never_repairs_legacy_alt2(tmp_path):
    db_path = tmp_path / "bootstrap.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_legacy_dependencies(conn)
        _create_legacy_alt2(conn)
        conn.exec_driver_sql(
            "INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 1)"
        )
        with pytest.raises(RuntimeError, match="schema incompatible"):
            ensure_weekview_schema(conn)
        assert conn.execute(text("SELECT COUNT(*) FROM weekview_alt2_flags")).scalar_one() == 1
    engine.dispose()


@pytest.mark.parametrize("defect", ("nullable_key", "partial_unique"))
def test_readiness_rejects_noncanonical_alt2_contract(tmp_path, defect):
    db_path = tmp_path / f"readiness-{defect}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _metadata().create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE weekview_alt2_flags")
        nullable = "department_id TEXT" if defect == "nullable_key" else "department_id TEXT NOT NULL"
        conn.exec_driver_sql(
            f"""
            CREATE TABLE weekview_alt2_flags (
                site_id TEXT NOT NULL,
                {nullable},
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        if defect == "partial_unique":
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX uq_partial_alt2 ON weekview_alt2_flags "
                "(site_id, department_id, year, week, day_of_week) WHERE enabled = 1"
            )
        with pytest.raises(RuntimeError, match="schema incompatible"):
            verify_weekview_schema(conn)
    engine.dispose()


def test_readiness_rejects_invalid_weekview_version_default(tmp_path):
    db_path = tmp_path / "readiness-invalid-version-default.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _metadata().create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE weekview_versions RENAME TO weekview_versions_original")
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_versions (
                tenant_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT -99,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, department_id, year, week)
            )
            """
        )
    with pytest.raises(RuntimeError, match="invalid required default"):
        verify_weekview_schema(engine)
    engine.dispose()


def test_readiness_rejects_sqlite_text_boolean_alt2_default(tmp_path):
    db_path = tmp_path / "readiness-text-boolean-default.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _metadata().create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE weekview_alt2_flags RENAME TO weekview_alt2_flags_original")
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_alt2_flags (
                site_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 'false',
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (site_id, department_id, year, week, day_of_week)
            )
            """
        )
    with pytest.raises(RuntimeError, match="invalid required default"):
        verify_weekview_schema(engine)
    engine.dispose()


def test_readiness_rejects_sqlite_now_timestamp_default_and_insert_fails(tmp_path):
    db_path = tmp_path / "readiness-now-timestamp-default.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _metadata().create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE weekview_versions RENAME TO weekview_versions_original")
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_versions (
                tenant_id INTEGER NOT NULL,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT (now()),
                PRIMARY KEY (tenant_id, department_id, year, week)
            )
            """
        )
        with pytest.raises(RuntimeError, match="invalid required default"):
            verify_weekview_schema(conn)
        with pytest.raises(Exception, match="unknown function: now"):
            conn.exec_driver_sql(
                "INSERT INTO weekview_versions(tenant_id, department_id, year, week) "
                "VALUES (1, 'dep-1', 2026, 6)"
            )
    engine.dispose()


def test_readiness_accepts_composite_primary_key_conflict_contract(tmp_path):
    db_path = tmp_path / "readiness-composite-primary-key.db"
    engine = create_engine(f"sqlite:///{db_path}")
    _metadata().create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE weekview_versions RENAME TO weekview_versions_original")
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_versions (
                tenant_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tenant_id, department_id, year, week)
            )
            """
        )
    verify_weekview_schema(engine)
    engine.dispose()


def test_downgrade_refuses_nonempty_business_tables(tmp_path):
    db_path = tmp_path / "downgrade.db"
    _stamp_0054(db_path)
    _upgrade(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO weekview_versions(tenant_id, department_id, year, week, version, updated_at) "
            "VALUES (7, 'dep-1', 2026, 6, 0, CURRENT_TIMESTAMP)"
        )
    engine.dispose()

    with pytest.raises(RuntimeError, match="downgrade refused"):
        _run_alembic(db_path, command.downgrade, "0054_add_menu_import_guards")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM weekview_versions")).scalar_one() == 1
    finally:
        engine.dispose()


def test_preflight_rejects_incompatible_table_before_legacy_alt2_changes(tmp_path):
    db_path = tmp_path / "preflight.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_legacy_dependencies(conn)
        _create_legacy_alt2(conn)
        conn.exec_driver_sql("INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 1)")
        conn.exec_driver_sql(
            """
            CREATE TABLE weekview_registrations (
                tenant_id TEXT, department_id TEXT NOT NULL, year INTEGER NOT NULL,
                week INTEGER NOT NULL, day_of_week INTEGER NOT NULL, meal TEXT NOT NULL,
                diet_type TEXT NOT NULL, marked INTEGER NOT NULL DEFAULT 0,
                UNIQUE(tenant_id, department_id, year, week, day_of_week, meal, diet_type)
            )
            """
        )
    engine.dispose()
    _stamp_0054(db_path)

    with pytest.raises(RuntimeError, match="schema incompatible"):
        _upgrade(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert "weekview_alt2_flags_new" not in inspect(conn).get_table_names()
            assert conn.execute(text("SELECT COUNT(*) FROM weekview_alt2_flags")).scalar_one() == 1
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0054_add_menu_import_guards"
    finally:
        engine.dispose()


def test_copy_failure_restores_legacy_alt2_and_cleans_owned_temporary_table(tmp_path, monkeypatch):
    db_path = tmp_path / "copy-failure.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_legacy_dependencies(conn)
        _create_legacy_alt2(conn)
        conn.exec_driver_sql("INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 1)")
    engine.dispose()
    _stamp_0054(db_path)

    from sqlalchemy.sql.expression import TableClause

    original_insert = TableClause.insert

    def fail_copy(self, *args, **kwargs):
        if self.name == "weekview_alt2_flags_new":
            raise RuntimeError("simulated copied-data failure")
        return original_insert(self, *args, **kwargs)

    monkeypatch.setattr(TableClause, "insert", fail_copy)
    with pytest.raises(RuntimeError, match="simulated copied-data failure"):
        _upgrade(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            assert "weekview_alt2_flags" in tables
            assert "weekview_alt2_flags_new" not in tables
            assert "weekview_alt2_flags_legacy_backup" not in tables
            assert conn.execute(text("SELECT COUNT(*) FROM weekview_alt2_flags")).scalar_one() == 1
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0054_add_menu_import_guards"
    finally:
        engine.dispose()


@pytest.mark.parametrize("with_row", (False, True))
def test_alembic_sqlite_transaction_rolls_back_complete_revision_and_allows_retry(
    tmp_path, monkeypatch, with_row
):
    db_path = tmp_path / f"transactional-revision-{with_row}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_legacy_dependencies(conn)
        _create_legacy_alt2(conn)
        if with_row:
            conn.exec_driver_sql(
                "INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 1)"
            )
    engine.dispose()
    _stamp_0054(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        before_tables = set(inspect(conn).get_table_names())
        before_columns = [
            column["name"] for column in inspect(conn).get_columns("weekview_alt2_flags")
        ]
        before_uniques = [
            tuple(item["column_names"])
            for item in inspect(conn).get_unique_constraints("weekview_alt2_flags")
        ]
        before_rows = conn.execute(
            text("SELECT tenant_id, department_id, year, week, day_of_week, is_alt2 FROM weekview_alt2_flags")
        ).all()
    engine.dispose()

    original_create_table = Operations.create_table

    def fail_versions_table(self, table_name, *args, **kwargs):
        if table_name == "weekview_versions":
            raise RuntimeError("simulated revision DDL failure")
        return original_create_table(self, table_name, *args, **kwargs)

    monkeypatch.setattr(Operations, "create_table", fail_versions_table)
    with pytest.raises(RuntimeError, match="simulated revision DDL failure"):
        _upgrade(db_path)
    monkeypatch.setattr(Operations, "create_table", original_create_table)

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) == before_tables
            assert [column["name"] for column in inspect(conn).get_columns("weekview_alt2_flags")] == before_columns
            assert [
                tuple(item["column_names"])
                for item in inspect(conn).get_unique_constraints("weekview_alt2_flags")
            ] == before_uniques
            assert conn.execute(
                text("SELECT tenant_id, department_id, year, week, day_of_week, is_alt2 FROM weekview_alt2_flags")
            ).all() == before_rows
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0054_add_menu_import_guards"
            assert "weekview_alt2_flags_new" not in inspect(conn).get_table_names()
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "failure_point",
    ("before_first_ddl", "after_copy", "after_first_rename", "after_second_rename", "after_backup_drop"),
)
def test_alembic_sqlite_rolls_back_each_legacy_alt2_failure_point(
    tmp_path, monkeypatch, failure_point
):
    db_path = tmp_path / f"failure-point-{failure_point}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        _create_legacy_dependencies(conn)
        _create_legacy_alt2(conn)
        conn.exec_driver_sql(
            "INSERT INTO weekview_alt2_flags VALUES (7, 'dep-1', 2026, 6, 1, 1)"
        )
    engine.dispose()
    _stamp_0054(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        before_tables = set(inspect(conn).get_table_names())
        before_columns = [
            column["name"] for column in inspect(conn).get_columns("weekview_alt2_flags")
        ]
        before_uniques = [
            tuple(item["column_names"])
            for item in inspect(conn).get_unique_constraints("weekview_alt2_flags")
        ]
        before_rows = conn.execute(text("SELECT * FROM weekview_alt2_flags")).all()
    engine.dispose()

    original_create_table = Operations.create_table
    original_rename_table = Operations.rename_table
    original_drop_table = Operations.drop_table
    rename_count = 0

    def create_table_failure(self, table_name, *args, **kwargs):
        if failure_point == "before_first_ddl" and table_name == "weekview_alt2_flags_new":
            raise RuntimeError("simulated failure before first DDL")
        return original_create_table(self, table_name, *args, **kwargs)

    def rename_failure(self, old_table_name, new_table_name, *args, **kwargs):
        nonlocal rename_count
        if failure_point == "after_copy" and rename_count == 0:
            raise RuntimeError("simulated failure after copy")
        rename_count += 1
        result = original_rename_table(self, old_table_name, new_table_name, *args, **kwargs)
        if failure_point == "after_first_rename" and rename_count == 1:
            raise RuntimeError("simulated failure after first rename")
        if failure_point == "after_second_rename" and rename_count == 2:
            raise RuntimeError("simulated failure after second rename")
        return result

    def drop_failure(self, table_name, *args, **kwargs):
        result = original_drop_table(self, table_name, *args, **kwargs)
        if failure_point == "after_backup_drop" and table_name == "weekview_alt2_flags_legacy_backup":
            raise RuntimeError("simulated failure after backup drop")
        return result

    monkeypatch.setattr(Operations, "create_table", create_table_failure)
    monkeypatch.setattr(Operations, "rename_table", rename_failure)
    monkeypatch.setattr(Operations, "drop_table", drop_failure)
    with pytest.raises(RuntimeError, match="simulated failure"):
        _upgrade(db_path)
    monkeypatch.undo()

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) == before_tables
            assert [column["name"] for column in inspect(conn).get_columns("weekview_alt2_flags")] == before_columns
            assert [
                tuple(item["column_names"])
                for item in inspect(conn).get_unique_constraints("weekview_alt2_flags")
            ] == before_uniques
            assert conn.execute(text("SELECT * FROM weekview_alt2_flags")).all() == before_rows
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0054_add_menu_import_guards"
    finally:
        engine.dispose()


def test_alembic_version_update_failure_rolls_back_revision(tmp_path):
    db_path = tmp_path / "version-update-failure.db"
    _stamp_0054(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TRIGGER fail_alembic_version_update
            BEFORE UPDATE ON alembic_version
            BEGIN
                SELECT RAISE(ABORT, 'simulated alembic version update failure');
            END
            """
        )
    engine.dispose()

    with pytest.raises(Exception, match="simulated alembic version update failure"):
        _upgrade(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        assert set(inspect(conn).get_table_names()) == {"alembic_version"}
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0054_add_menu_import_guards"
        conn.exec_driver_sql("DROP TRIGGER fail_alembic_version_update")
    engine.dispose()

    _upgrade(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
    finally:
        engine.dispose()

    _upgrade(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
    finally:
        engine.dispose()

    _upgrade(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0055_weekview_schema"
            assert set(EXPECTED_TABLES).issubset(inspect(conn).get_table_names())
    finally:
        engine.dispose()
