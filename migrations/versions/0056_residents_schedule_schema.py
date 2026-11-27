"""Provision residents schedules with distinct weekly and forever keys."""

from alembic import op
import sqlalchemy as sa

revision = "0056_residents_schedule_schema"
down_revision = "0055_weekview_schema"
branch_labels = None
depends_on = None


def _validate_columns(conn, table, expected, required):
    columns = {column["name"]: column for column in sa.inspect(conn).get_columns(table)}
    for name, kind in expected.items():
        if name not in columns or not isinstance(columns[name]["type"], kind):
            raise RuntimeError(f"Incompatible residents schema: {table}.{name}")
        if name in required and columns[name]["nullable"]:
            raise RuntimeError(f"Incompatible residents schema: {table}.{name} must be NOT NULL")
        if conn.dialect.name == "sqlite":
            value_type = "integer" if issubclass(kind, sa.Integer) else "text"
            if conn.execute(sa.text(
                f"SELECT 1 FROM {table} WHERE {name} IS NOT NULL "
                f"AND typeof({name}) != :value_type LIMIT 1"
            ), {"value_type": value_type}).first():
                raise RuntimeError(f"Incompatible residents value: {table}.{name}")
    for name, column in columns.items():
        if name not in expected and not column["nullable"] and column["default"] is None:
            raise RuntimeError(f"Incompatible required residents column: {table}.{name}")
    return columns


def _reject_duplicates(conn, table, keys):
    key_list = ", ".join(keys)
    if conn.execute(sa.text(
        f"SELECT 1 FROM {table} GROUP BY {key_list} HAVING COUNT(*) > 1 LIMIT 1"
    )).first():
        raise RuntimeError(f"Ambiguous duplicate residents rows: {table}")


def _create_index(conn, name, table, keys, predicate=None):
    indexes = {index["name"]: index for index in sa.inspect(conn).get_indexes(table)}
    if name in indexes:
        raise RuntimeError(f"Unexpected existing residents index: {name}")
    options = {}
    if predicate:
        options = {"sqlite_where": sa.text(predicate), "postgresql_where": sa.text(predicate)}
    op.create_index(name, table, keys, unique=True, **options)


def upgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    schedule = "department_residents_schedule"
    weekly = "department_residents_weekly"
    if schedule in tables:
        _validate_columns(conn, schedule, {
            "department_id": sa.String, "week": sa.Integer, "weekday": sa.Integer,
            "meal": sa.String, "count": sa.Integer,
        }, {"department_id", "weekday", "meal", "count"})
        pk = sa.inspect(conn).get_pk_constraint(schedule)
        if pk.get("constrained_columns") and pk["constrained_columns"] != [
            "department_id", "week", "weekday", "meal"
        ]:
            raise RuntimeError("Incompatible residents schedule primary key")
        _reject_duplicates(conn, schedule, ("department_id", "week", "weekday", "meal"))
    if weekly in tables:
        _validate_columns(conn, weekly, {
            "id": sa.String, "department_id": sa.String, "year": sa.Integer,
            "week": sa.Integer, "residents_lunch": sa.Integer,
            "residents_dinner": sa.Integer, "updated_at": sa.String,
        }, {"department_id", "year", "week"})
        _reject_duplicates(conn, weekly, ("department_id", "year", "week"))
    if schedule not in tables:
        op.create_table(
            schedule,
            sa.Column("department_id", sa.Text(), nullable=False),
            sa.Column("week", sa.Integer(), nullable=True),
            sa.Column("weekday", sa.Integer(), nullable=False),
            sa.Column("meal", sa.Text(), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False),
        )
    else:
        columns = _validate_columns(conn, schedule, {
            "department_id": sa.String, "week": sa.Integer, "weekday": sa.Integer,
            "meal": sa.String, "count": sa.Integer,
        }, {"department_id", "weekday", "meal", "count"})
        pk = sa.inspect(conn).get_pk_constraint(schedule)
        if conn.dialect.name == "postgresql" and "week" in (pk.get("constrained_columns") or ()):
            if pk.get("constrained_columns") != ["department_id", "week", "weekday", "meal"] or not pk.get("name"):
                raise RuntimeError("Incompatible residents schedule primary key")
            op.drop_constraint(pk["name"], schedule, type_="primary")
        if not columns["week"]["nullable"]:
            if conn.dialect.name != "postgresql":
                raise RuntimeError("Residents schedule week must be nullable")
            op.alter_column(schedule, "week", existing_type=sa.Integer(), nullable=True)
    _create_index(conn, "ux_residents_schedule_week", schedule,
                  ["department_id", "week", "weekday", "meal"], "week IS NOT NULL")
    _create_index(conn, "ux_residents_schedule_forever", schedule,
                  ["department_id", "weekday", "meal"], "week IS NULL")

    if weekly not in tables:
        op.create_table(
            weekly,
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("department_id", sa.Text(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("week", sa.Integer(), nullable=False),
            sa.Column("residents_lunch", sa.Integer()),
            sa.Column("residents_dinner", sa.Integer()),
            sa.Column("updated_at", sa.Text()),
        )
    else:
        _validate_columns(conn, weekly, {
            "id": sa.String, "department_id": sa.String, "year": sa.Integer,
            "week": sa.Integer, "residents_lunch": sa.Integer,
            "residents_dinner": sa.Integer, "updated_at": sa.String,
        }, {"department_id", "year", "week"})
    indexes = {index["name"]: index for index in sa.inspect(conn).get_indexes(weekly)}
    if "ux_dept_res_week" in indexes:
        index = indexes["ux_dept_res_week"]
        where = index.get("dialect_options", {}).get(f"{conn.dialect.name}_where")
        if not index["unique"] or index["column_names"] != ["department_id", "year", "week"] or where is not None:
            raise RuntimeError("Incompatible residents weekly index")
    else:
        _create_index(conn, "ux_dept_res_week", weekly, ["department_id", "year", "week"])


def downgrade():
    raise RuntimeError("Residents schedule migration cannot be downgraded without risking data loss")
