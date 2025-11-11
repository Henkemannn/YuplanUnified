"""Admin Phase B: sites, departments, diet types, department diet defaults + version columns

Revision ID: 0008_admin_phase_b
Revises: 0007_add_task_timestamps
Create Date: 2025-11-10

This migration introduces the persistence layer for Admin Phase B:
  * New tables: sites, departments, diet_types, department_diet_defaults
  * Adds version + updated_at columns (if missing) to: notes, weekview_alt2_flags
  * Adds version (if missing) to weekview_alt2_flags (created previously ad-hoc) and notes
  * Postgres: shared trigger function bump_version_updated_at() + BEFORE INSERT OR UPDATE triggers per table
  * SQLite: version + updated_at columns only (version bumps will be handled in repository logic for simplicity)

Implementation notes:
  * We use TEXT uuid columns for cross‑dialect portability instead of native UUID.
  * weekview_alt2_flags table may have been created outside Alembic; we defensively ALTER if present.
  * Triggers on DELETE are omitted – row is removed so version bump is not meaningful.
  * For idempotency we DROP existing triggers first (Postgres) before re‑creating.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0008_admin_phase_b"
down_revision = "0007_add_task_timestamps"
branch_labels = None
depends_on = None

TABLES_VERSIONED = [
    "sites",
    "departments",
    "diet_types",
    "department_diet_defaults",
    "notes",
    "weekview_alt2_flags",
    "alt2_flags",
]


def _ensure_table_sites(inspector):
    if "sites" in inspector.get_table_names():
        return
    # Sites has only inline unique constraint on name; no separate index needed.
    op.create_table(
        "sites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.UniqueConstraint("name", name="uq_sites_name"),
    )
    # Inline unique constraint ensures uniqueness across dialects.


def _ensure_table_diet_types(inspector):
    if "diet_types" in inspector.get_table_names():
        return
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else "sqlite"
    false_def = sa.text("FALSE") if dialect == "postgresql" else sa.text("0")
    op.create_table(
        "diet_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("premarked", sa.Boolean(), server_default=false_def, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
    )


def _ensure_table_departments(inspector):
    if "departments" in inspector.get_table_names():
        return
    conn = op.get_bind()
    # Resident counts use INTEGER defaults; no dialect boolean handling needed here.
    op.create_table(
        "departments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("resident_count_mode", sa.String(32), nullable=False),
        sa.Column("resident_count_fixed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.UniqueConstraint("site_id", "name", name="uq_departments_site_name"),
    )
    op.create_index("ix_departments_site_id", "departments", ["site_id"])


def _ensure_table_department_diet_defaults(inspector):
    if "department_diet_defaults" in inspector.get_table_names():
        return
    conn = op.get_bind()
    op.create_table(
        "department_diet_defaults",
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("diet_type_id", sa.String(36), sa.ForeignKey("diet_types.id"), nullable=False),
        sa.Column("default_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("department_id", "diet_type_id", name="pk_department_diet_defaults"),
    )
    op.create_index("ix_department_diet_defaults_department", "department_diet_defaults", ["department_id"])


def _ensure_version_columns(inspector):
    for tbl in ["notes", "weekview_alt2_flags"]:
        if tbl in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns(tbl)}
            if "version" not in cols:
                op.add_column(tbl, sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False))
            if "updated_at" not in cols:
                # Use CURRENT_TIMESTAMP for portability
                op.add_column(tbl, sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))


def _create_postgres_function_and_triggers(conn):
    dialect = conn.dialect.name
    if dialect != "postgresql":
        return
    # Shared function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION bump_version_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.version := COALESCE(OLD.version, 0) + 1;
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    for tbl in TABLES_VERSIONED:
        if tbl not in existing_tables:
            continue
        # Drop + recreate trigger idempotently
        trig_name = f"{tbl}_version_bump_trg"
        op.execute(f"DROP TRIGGER IF EXISTS {trig_name} ON {tbl};")
        op.execute(
            f"CREATE TRIGGER {trig_name} BEFORE INSERT OR UPDATE ON {tbl} FOR EACH ROW EXECUTE FUNCTION bump_version_updated_at();"
        )


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    # Create/ensure core tables first (FK deps)
    _ensure_table_sites(inspector)
    _ensure_table_diet_types(inspector)
    _ensure_table_departments(inspector)
    _ensure_table_department_diet_defaults(inspector)
    # Alt2 flags (Phase B bulk persistence) after deps exist
    if "alt2_flags" not in inspector.get_table_names():
        dialect = conn.dialect.name if conn is not None else "sqlite"
        true_def = sa.text("TRUE") if dialect == "postgresql" else sa.text("1")
        op.create_table(
            "alt2_flags",
            sa.Column("site_id", sa.String(36), nullable=False),
            sa.Column("department_id", sa.String(36), nullable=False),
            sa.Column("week", sa.Integer(), nullable=False),
            sa.Column("weekday", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), server_default=true_def, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
            sa.PrimaryKeyConstraint("site_id", "department_id", "week", "weekday", name="pk_alt2_flags"),
            sa.CheckConstraint("week BETWEEN 1 AND 53", name="ck_alt2_week_range"),
            sa.CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_alt2_weekday_range"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_alt2_flags_dept_week", "alt2_flags", ["department_id", "week"])
        op.create_index("ix_alt2_flags_week_dept_weekday", "alt2_flags", ["week", "department_id", "weekday"])
    # Ensure version columns on pre-existing tables
    _ensure_version_columns(inspector)
    # Postgres: triggers
    _create_postgres_function_and_triggers(conn)
    # SQLite: add AFTER UPDATE triggers to bump version and updated_at and create weekview_alt2_flags if missing
    if conn.dialect.name == "sqlite":
        # Ensure weekview_alt2_flags exists for SQLite (tests rely on repo, but be defensive here)
        if "weekview_alt2_flags" not in inspector.get_table_names():
            op.create_table(
                "weekview_alt2_flags",
                sa.Column("tenant_id", sa.Text(), nullable=False),
                sa.Column("department_id", sa.Text(), nullable=False),
                sa.Column("year", sa.Integer(), nullable=False),
                sa.Column("week", sa.Integer(), nullable=False),
                sa.Column("day_of_week", sa.Integer(), nullable=False),
                    sa.Column("is_alt2", sa.Integer(), server_default=sa.text("0"), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
                sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
            )
            op.create_unique_constraint(
                "uq_weekview_alt2_flags",
                "weekview_alt2_flags",
                ["tenant_id", "department_id", "year", "week", "day_of_week"],
            )
        # Create AFTER UPDATE triggers to emulate version bump
        def _sqlite_trigger(tbl: str):
            trig = f"{tbl}_version_bump_trg"
            op.execute(f"DROP TRIGGER IF EXISTS {trig};")
            op.execute(
                f"""
                CREATE TRIGGER {trig}
                AFTER UPDATE ON {tbl}
                FOR EACH ROW
                BEGIN
                    UPDATE {tbl}
                    SET version = COALESCE(version, 0) + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rowid = NEW.rowid;
                END;
                """
            )
        for t in TABLES_VERSIONED:
            if t in inspector.get_table_names():
                _sqlite_trigger(t)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    # Drop triggers first (Postgres)
    if dialect == "postgresql":
        for tbl in TABLES_VERSIONED:
            if tbl in existing_tables:
                trig_name = f"{tbl}_version_bump_trg"
                op.execute(f"DROP TRIGGER IF EXISTS {trig_name} ON {tbl};")
        op.execute("DROP FUNCTION IF EXISTS bump_version_updated_at();")
    elif dialect == "sqlite":
        for tbl in TABLES_VERSIONED:
            trig_name = f"{tbl}_version_bump_trg"
            op.execute(f"DROP TRIGGER IF EXISTS {trig_name};")
    # Drop new tables (reverse order for FK constraints)
    if "department_diet_defaults" in existing_tables:
        op.drop_index("ix_department_diet_defaults_department", table_name="department_diet_defaults")
        op.drop_table("department_diet_defaults")
    if "departments" in existing_tables:
        op.drop_index("ix_departments_site_id", table_name="departments")
        op.drop_table("departments")
    if "diet_types" in existing_tables:
        op.drop_table("diet_types")
    if "sites" in existing_tables:
        # Unique constraint dropped implicitly with table
        op.drop_table("sites")
    # Remove added columns (best-effort)
    for tbl in ["notes", "weekview_alt2_flags"]:
        if tbl in existing_tables:
            cols = {c["name"] for c in inspector.get_columns(tbl)}
            if "version" in cols:
                try:
                    op.drop_column(tbl, "version")
                except Exception:
                    pass
            # We do NOT drop updated_at if it pre-existed; only attempt if we added it and table originally lacked.
            # (No reliable annotation kept; leave updated_at to avoid data loss.)
