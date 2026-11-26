"""Provision the canonical Weekview schema.

Revision ID: 0055_weekview_schema
Revises: 0054_add_menu_import_guards
"""
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision = "0055_weekview_schema"
down_revision = "0054_add_menu_import_guards"
branch_labels = None
depends_on = None


TABLE_CONTRACTS = {
    "weekview_registrations": (
        ("tenant_id", sa.Integer(), False),
        ("department_id", sa.Text(), False),
        ("year", sa.Integer(), False),
        ("week", sa.Integer(), False),
        ("day_of_week", sa.Integer(), False),
        ("meal", sa.Text(), False),
        ("diet_type", sa.Text(), False),
        ("marked", sa.Integer(), False),
        ("updated_at", sa.DateTime(timezone=True), False),
    ),
    "weekview_versions": (
        ("tenant_id", sa.Integer(), False),
        ("department_id", sa.Text(), False),
        ("year", sa.Integer(), False),
        ("week", sa.Integer(), False),
        ("version", sa.Integer(), False),
        ("updated_at", sa.DateTime(timezone=True), False),
    ),
    "weekview_residents_count": (
        ("tenant_id", sa.Integer(), False),
        ("department_id", sa.Text(), False),
        ("year", sa.Integer(), False),
        ("week", sa.Integer(), False),
        ("day_of_week", sa.Integer(), False),
        ("meal", sa.Text(), False),
        ("count", sa.Integer(), False),
        ("updated_at", sa.DateTime(timezone=True), False),
    ),
    "weekview_alt2_flags": (
        ("site_id", sa.Text(), False),
        ("department_id", sa.Text(), False),
        ("year", sa.Integer(), False),
        ("week", sa.Integer(), False),
        ("day_of_week", sa.Integer(), False),
        ("enabled", sa.Integer(), False),
        ("updated_at", sa.DateTime(timezone=True), False),
    ),
}

UNIQUE_KEYS = {
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
    "weekview_alt2_flags": ("site_id", "department_id", "year", "week", "day_of_week"),
}


def _create_table(name: str, *, contract_name: str | None = None) -> None:
    contract_name = contract_name or name
    dialect = op.get_bind().dialect.name
    defaults = {
        "marked": sa.text("0"),
        "count": sa.text("0"),
        "version": sa.text("0"),
        "enabled": sa.text("FALSE" if dialect == "postgresql" else "0"),
        "updated_at": sa.text("CURRENT_TIMESTAMP"),
    }
    columns = [
        sa.Column(
            column_name,
            sa.Boolean() if column_name == "enabled" and dialect == "postgresql" else column_type,
            nullable=nullable,
            server_default=defaults.get(column_name),
        )
        for column_name, column_type, nullable in TABLE_CONTRACTS[contract_name]
    ]
    op.create_table(
        name,
        *columns,
        sa.UniqueConstraint(*UNIQUE_KEYS[contract_name], name=f"uq_{name}_business_key"),
    )


def _unique_keys(inspector, table_name: str) -> set[tuple[str, ...]]:
    keys = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint.get("column_names")
    }
    keys.update(
        tuple(index["column_names"])
        for index in inspector.get_indexes(table_name)
        if index.get("unique")
        and index.get("column_names")
        and not any(
            index.get("dialect_options", {}).get(key) is not None
            for key in ("sqlite_where", "postgresql_where")
        )
    )
    return keys


def _has_conflict_key(inspector, table_name: str) -> bool:
    unique_columns = UNIQUE_KEYS[table_name]
    primary_key = tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
    if primary_key == unique_columns:
        return True
    return unique_columns in _unique_keys(inspector, table_name)


def _valid_default(column_name: str, default, dialect: str) -> bool:
    normalized = str(default).strip().lower()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    normalized = normalized.replace("::text", "").replace("::integer", "").replace("::boolean", "")
    if column_name in {"marked", "count", "version"}:
        return normalized in {"0", "0.0"}
    if column_name == "enabled":
        if dialect == "postgresql":
            return normalized in {"false", "'false'"}
        return normalized in {"0", "0.0"}
    if column_name == "updated_at":
        if dialect == "postgresql":
            return normalized in {"current_timestamp", "current_timestamp()", "now()"}
        return normalized in {"current_timestamp", "current_timestamp()"}
    return True


def _verify_table(conn, table_name: str, *, allow_missing_updated_at: bool = False) -> None:
    inspector = inspect(conn)
    columns = {column["name"]: column for column in inspector.get_columns(table_name)}
    required = {column[0] for column in TABLE_CONTRACTS[table_name]}
    if allow_missing_updated_at:
        required.discard("updated_at")
    if not required.issubset(columns):
        raise RuntimeError("Weekview schema incompatible: required column missing")
    if table_name == "weekview_alt2_flags" and {"tenant_id", "is_alt2"}.intersection(columns):
        raise RuntimeError("Weekview schema incompatible: legacy columns present")
    integer_columns = {
        "tenant_id",
        "year",
        "week",
        "day_of_week",
        "marked",
        "count",
        "version",
        "enabled",
    }
    text_columns = {"department_id", "site_id", "meal", "diet_type"}
    for column_name in required:
        type_name = str(columns[column_name]["type"]).upper()
        if column_name in integer_columns:
            if column_name == "tenant_id" and conn.dialect.name == "sqlite":
                valid = any(marker in type_name for marker in ("INT", "CHAR", "TEXT", "CLOB"))
            elif column_name == "enabled" and conn.dialect.name == "postgresql":
                valid = "BOOL" in type_name
            else:
                valid = "INT" in type_name
            if not valid:
                raise RuntimeError("Weekview schema incompatible: column type mismatch")
        if column_name in text_columns and not any(
            marker in type_name for marker in ("CHAR", "TEXT", "CLOB")
        ):
            raise RuntimeError("Weekview schema incompatible: column type mismatch")
        if column_name == "updated_at" and not any(
            marker in type_name for marker in ("DATE", "TIME")
        ):
            raise RuntimeError("Weekview schema incompatible: column type mismatch")
    for column_name in required:
        if columns[column_name].get("nullable", True):
            raise RuntimeError("Weekview schema incompatible: nullable key column")
        if column_name in {"marked", "count", "version", "enabled", "updated_at"}:
            default = columns[column_name].get("default")
            if default is None or not _valid_default(column_name, default, conn.dialect.name):
                raise RuntimeError(
                    f"Weekview schema incompatible: invalid required default for {table_name}.{column_name}"
                )
    for column_name, column in columns.items():
        if column_name not in {item[0] for item in TABLE_CONTRACTS[table_name]} and not column.get(
            "nullable", True
        ) and column.get("default") is None:
            raise RuntimeError("Weekview schema incompatible: unsupported required column")
    if not _has_conflict_key(inspector, table_name):
        raise RuntimeError("Weekview schema incompatible: required unique key missing")


def _add_updated_at_if_missing(conn, table_name: str) -> None:
    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "updated_at" not in columns:
        column = sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        if conn.dialect.name == "sqlite":
            with op.batch_alter_table(table_name, recreate="always") as batch_op:
                batch_op.add_column(column)
            return
        op.add_column(
            table_name,
            column,
        )


def _legacy_alt2_rows(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT w.tenant_id, w.department_id, w.year, w.week, w.day_of_week, w.is_alt2,
                   d.site_id, s.tenant_id AS site_tenant_id
            FROM weekview_alt2_flags w
            LEFT JOIN departments d ON CAST(d.id AS TEXT) = CAST(w.department_id AS TEXT)
            LEFT JOIN sites s ON CAST(s.id AS TEXT) = CAST(d.site_id AS TEXT)
            ORDER BY w.department_id, w.year, w.week, w.day_of_week
            """
        )
    ).mappings().all()
    result: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for row in rows:
        site_id = row["site_id"]
        site_tenant_id = row["site_tenant_id"]
        tenant_id = row["tenant_id"]
        key = (site_id, row["department_id"], row["year"], row["week"], row["day_of_week"])
        if (
            site_id is None
            or site_tenant_id is None
            or tenant_id is None
            or str(site_tenant_id) != str(tenant_id)
            or row["is_alt2"] is None
            or not isinstance(row["is_alt2"], (bool, int))
            or int(row["is_alt2"]) not in (0, 1)
            or key in seen
        ):
            raise RuntimeError("Weekview legacy Alt2 migration aborted: relation or conflict validation failed")
        seen.add(key)
        result.append(
            {
                "site_id": site_id,
                "department_id": row["department_id"],
                "year": row["year"],
                "week": row["week"],
                "day_of_week": row["day_of_week"],
                "enabled": (
                    bool(row["is_alt2"])
                    if conn.dialect.name == "postgresql"
                    else 1 if bool(row["is_alt2"]) else 0
                ),
                "updated_at": datetime.now(UTC),
            }
        )
    if len(result) != len(seen):
        raise RuntimeError("Weekview legacy Alt2 migration aborted: duplicate validation failed")
    return result


def _validate_upgrade_preconditions(conn) -> None:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    for table_name in TABLE_CONTRACTS:
        if table_name not in tables:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if table_name == "weekview_alt2_flags":
            canonical = {"site_id", "enabled"}.issubset(columns)
            legacy = {"tenant_id", "department_id", "year", "week", "day_of_week", "is_alt2"}.issubset(
                columns
            )
            if canonical and legacy:
                raise RuntimeError("Weekview schema incompatible: hybrid Alt2 schema")
            if legacy:
                _legacy_alt2_rows(conn)
                continue
            if not canonical:
                raise RuntimeError("Weekview legacy Alt2 migration aborted: unknown schema")
        _verify_table(conn, table_name, allow_missing_updated_at=True)


def _lock_postgresql_sources(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    existing = set(inspect(conn).get_table_names())
    tables = [
        table_name
        for table_name in ("sites", "departments", "weekview_alt2_flags")
        if table_name in existing
    ]
    if tables:
        conn.execute(
            text("LOCK TABLE " + ", ".join(tables) + " IN SHARE ROW EXCLUSIVE MODE")
        )


def _migrate_legacy_alt2(conn) -> None:
    inspector = inspect(conn)
    if "weekview_alt2_flags" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("weekview_alt2_flags")}
    if {"site_id", "enabled"}.issubset(columns) and not {"tenant_id", "is_alt2"}.intersection(columns):
        _add_updated_at_if_missing(conn, "weekview_alt2_flags")
        _verify_table(conn, "weekview_alt2_flags")
        return
    if {"site_id", "enabled"}.intersection(columns) and {"tenant_id", "is_alt2"}.intersection(columns):
        raise RuntimeError("Weekview schema incompatible: hybrid Alt2 schema")
    if not {"tenant_id", "department_id", "year", "week", "day_of_week", "is_alt2"}.issubset(columns):
        raise RuntimeError("Weekview legacy Alt2 migration aborted: unknown schema")

    rows = _legacy_alt2_rows(conn)
    temporary = "weekview_alt2_flags_new"
    if temporary in inspector.get_table_names():
        raise RuntimeError("Weekview legacy Alt2 migration aborted: temporary table already exists")
    backup = "weekview_alt2_flags_legacy_backup"
    if backup in inspector.get_table_names():
        raise RuntimeError("Weekview legacy Alt2 migration aborted: backup table already exists")
    _create_table(temporary, contract_name="weekview_alt2_flags")
    table = sa.table(
        temporary,
        sa.column("site_id", sa.Text()),
        sa.column("department_id", sa.Text()),
        sa.column("year", sa.Integer()),
        sa.column("week", sa.Integer()),
        sa.column("day_of_week", sa.Integer()),
        sa.column(
            "enabled",
            sa.Boolean() if conn.dialect.name == "postgresql" else sa.Integer(),
        ),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    if rows:
        conn.execute(table.insert(), rows)
    copied = conn.execute(
        text(
            f"SELECT site_id, department_id, year, week, day_of_week, enabled "
            f"FROM {temporary} ORDER BY department_id, year, week, day_of_week"
        )
    ).mappings().all()
    expected = sorted(
        rows,
        key=lambda row: (row["department_id"], row["year"], row["week"], row["day_of_week"]),
    )
    actual = [dict(row) for row in copied]
    expected_without_timestamp = [
        {key: value for key, value in row.items() if key != "updated_at"}
        for row in expected
    ]
    if actual != expected_without_timestamp:
        raise RuntimeError("Weekview legacy Alt2 migration aborted: copied data verification failed")
    op.rename_table("weekview_alt2_flags", backup)
    op.rename_table(temporary, "weekview_alt2_flags")
    _verify_table(conn, "weekview_alt2_flags")
    op.drop_table(backup)


def _create_timestamp_triggers(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION weekview_set_updated_at_v2()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION weekview_bump_version_v2()
        RETURNS TRIGGER AS $$
        DECLARE
            v_tenant INTEGER;
            v_department TEXT;
            v_year INTEGER;
            v_week INTEGER;
        BEGIN
            v_department := COALESCE(NEW.department_id, OLD.department_id);
            v_year := COALESCE(NEW.year, OLD.year);
            v_week := COALESCE(NEW.week, OLD.week);
            IF TG_TABLE_NAME = 'weekview_alt2_flags' THEN
                SELECT s.tenant_id INTO v_tenant
                FROM departments d
                JOIN sites s ON s.id = d.site_id
                WHERE d.id = v_department
                  AND s.id = COALESCE(NEW.site_id, OLD.site_id);
            ELSE
                v_tenant := COALESCE(NEW.tenant_id, OLD.tenant_id);
            END IF;
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'Weekview version scope could not be resolved';
            END IF;
            UPDATE weekview_versions
            SET version = version + 1, updated_at = now()
            WHERE tenant_id = v_tenant
              AND department_id = v_department
              AND year = v_year
              AND week = v_week;
            IF NOT FOUND THEN
                INSERT INTO weekview_versions(tenant_id, department_id, year, week, version)
                VALUES(v_tenant, v_department, v_year, v_week, 1)
                ON CONFLICT (tenant_id, department_id, year, week)
                DO UPDATE SET version = weekview_versions.version + 1, updated_at = now();
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table_name in TABLE_CONTRACTS:
        old_names = (
            f"trg_wv_{'reg' if table_name == 'weekview_registrations' else 'res' if table_name == 'weekview_residents_count' else 'alt2'}_updated_at",
            f"trg_wv_{'reg' if table_name == 'weekview_registrations' else 'res' if table_name == 'weekview_residents_count' else 'alt2'}_bump_version",
            f"{table_name}_version_bump_trg",
        )
        for old_name in old_names:
            op.execute(f"DROP TRIGGER IF EXISTS {old_name} ON {table_name}")
        timestamp_trigger = f"trg_{table_name}_updated_at_v2"
        version_trigger = f"trg_{table_name}_bump_version_v2"
        op.execute(f"DROP TRIGGER IF EXISTS {timestamp_trigger} ON {table_name}")
        op.execute(f"DROP TRIGGER IF EXISTS {version_trigger} ON {table_name}")
        op.execute(
            f"CREATE TRIGGER {timestamp_trigger} BEFORE UPDATE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION weekview_set_updated_at_v2()"
        )
        if table_name != "weekview_versions":
            op.execute(
                f"CREATE TRIGGER {version_trigger} AFTER INSERT OR UPDATE OR DELETE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION weekview_bump_version_v2()"
            )


def upgrade() -> None:
    conn = op.get_bind()
    _lock_postgresql_sources(conn)
    inspector = inspect(conn)
    _validate_upgrade_preconditions(conn)
    _migrate_legacy_alt2(conn)
    inspector = inspect(conn)
    for table_name in TABLE_CONTRACTS:
        if table_name not in inspector.get_table_names():
            _create_table(table_name)
        else:
            _add_updated_at_if_missing(conn, table_name)
        _verify_table(conn, table_name)
    _create_timestamp_triggers(conn)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    for table_name in TABLE_CONTRACTS:
        if table_name in inspector.get_table_names():
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
            if count:
                raise RuntimeError("Weekview downgrade refused: business data must be exported first")
    if conn.dialect.name == "postgresql":
        for table_name in TABLE_CONTRACTS:
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at_v2 ON {table_name}")
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_bump_version_v2 ON {table_name}")
        op.execute("DROP FUNCTION IF EXISTS weekview_set_updated_at_v2()")
        op.execute("DROP FUNCTION IF EXISTS weekview_bump_version_v2()")
    for table_name in reversed(tuple(TABLE_CONTRACTS)):
        if table_name in inspect(conn).get_table_names():
            op.drop_table(table_name)
