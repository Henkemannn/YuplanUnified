"""Provision meal registrations without runtime DDL."""

from alembic import op
import sqlalchemy as sa

revision = "0057_meal_registrations_schema"
down_revision = "0056_residents_schedule_schema"
branch_labels = None
depends_on = None

KEY = ["tenant_id", "site_id", "department_id", "date", "meal_type"]


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "meal_registrations" not in inspector.get_table_names():
        op.create_table(
            "meal_registrations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.Text(), nullable=False),
            sa.Column("department_id", sa.Text(), nullable=False),
            sa.Column("date", sa.Text(), nullable=False),
            sa.Column("meal_type", sa.Text(), nullable=False),
            sa.Column("registered", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_at", sa.Text()),
            sa.UniqueConstraint(*KEY, name="uq_meal_registrations_scope"),
        )
        return

    columns = {column["name"]: column for column in inspector.get_columns("meal_registrations")}
    expected = {
        "id": sa.Integer, "tenant_id": sa.Integer, "site_id": sa.String,
        "department_id": sa.String, "date": sa.String, "meal_type": sa.String,
        "registered": sa.Integer, "updated_at": sa.String,
    }
    for name, kind in expected.items():
        if (name not in columns or not isinstance(columns[name]["type"], kind)
                or (name in (*KEY, "registered") and columns[name]["nullable"])):
            raise RuntimeError(f"Incompatible meal registrations schema: {name}")
    if inspector.get_pk_constraint("meal_registrations").get("constrained_columns") != ["id"]:
        raise RuntimeError("Incompatible meal registrations primary key")
    if conn.dialect.name == "sqlite":
        table_info = conn.exec_driver_sql("PRAGMA table_info('meal_registrations')").all()
        indexes = conn.exec_driver_sql("PRAGMA index_list('meal_registrations')").all()
        id_type = next(row[2] for row in table_info if row[1] == "id")
        if id_type.strip().upper() != "INTEGER" or any(row[3] == "pk" for row in indexes):
            raise RuntimeError("Meal registrations id must be an SQLite rowid alias")
    if conn.dialect.name == "postgresql" and not (
        columns["id"].get("identity") or columns["id"].get("default")
    ):
        raise RuntimeError("Meal registrations id must be generated")
    if conn.dialect.name == "postgresql":
        sequence = conn.execute(sa.text(
            "SELECT pg_get_serial_sequence('meal_registrations', 'id')"
        )).scalar_one()
        maximum = conn.execute(sa.text("SELECT max(id) FROM meal_registrations")).scalar_one()
        if not sequence:
            raise RuntimeError("Meal registrations id must use a sequence")
        increment, cycle = conn.execute(sa.text(
            "SELECT seqincrement, seqcycle FROM pg_sequence WHERE seqrelid=CAST(:sequence AS regclass)"
        ), {"sequence": sequence}).one()
        if increment <= 0 or cycle:
            raise RuntimeError("Incompatible meal registrations id sequence")
        if maximum is not None:
            last = conn.execute(sa.text(
                "SELECT pg_sequence_last_value(CAST(:sequence AS regclass))"
            ), {"sequence": sequence}).scalar_one()
            if last is None or last < maximum:
                raise RuntimeError("Meal registrations id sequence is behind existing data")
    unique = inspector.get_unique_constraints("meal_registrations")
    indexes = inspector.get_indexes("meal_registrations")
    if not any(item.get("column_names") == KEY for item in unique) and not any(
        item.get("unique") and item.get("column_names") == KEY
        and item.get("dialect_options", {}).get(f"{conn.dialect.name}_where") is None
        for item in indexes
    ):
        raise RuntimeError("Incompatible meal registrations unique key")
    for name, column in columns.items():
        if name not in expected and not column["nullable"] and column["default"] is None:
            raise RuntimeError(f"Incompatible required meal registrations column: {name}")
    if conn.execute(sa.text(
        "SELECT 1 FROM meal_registrations WHERE registered NOT IN (0, 1) LIMIT 1"
    )).first():
        raise RuntimeError("Incompatible meal registration value")
    if conn.dialect.name == "sqlite":
        for name, kind in expected.items():
            value_type = "integer" if issubclass(kind, sa.Integer) else "text"
            if conn.execute(sa.text(
                f"SELECT 1 FROM meal_registrations WHERE {name} IS NOT NULL "
                f"AND typeof({name}) != :kind LIMIT 1"
            ), {"kind": value_type}).first():
                raise RuntimeError(f"Incompatible meal registration value: {name}")


def downgrade():
    raise RuntimeError("Meal registrations migration cannot be downgraded without risking data loss")
