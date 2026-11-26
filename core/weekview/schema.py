from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, Table, Text, UniqueConstraint, text
from sqlalchemy.exc import SQLAlchemyError


class WeekviewSchemaError(RuntimeError):
    """Raised when the required canonical Weekview schema is unavailable."""


WEEKVIEW_TABLES = (
    "weekview_registrations",
    "weekview_versions",
    "weekview_residents_count",
    "weekview_alt2_flags",
)


def _metadata(dialect: str = "sqlite") -> MetaData:
    metadata = MetaData()
    Table(
        "weekview_registrations",
        metadata,
        _tenant_column(),
        _department_column(),
        _year_column(),
        _week_column(),
        _day_column(),
        _meal_column(),
        _diet_type_column(),
        _marked_column(),
        _updated_at_column(),
        UniqueConstraint(
            "tenant_id",
            "department_id",
            "year",
            "week",
            "day_of_week",
            "meal",
            "diet_type",
            name="uq_weekview_registrations_business_key",
        ),
    )
    Table(
        "weekview_versions",
        metadata,
        _tenant_column(),
        _department_column(),
        _year_column(),
        _week_column(),
        _version_column(),
        _updated_at_column(),
        UniqueConstraint(
            "tenant_id",
            "department_id",
            "year",
            "week",
            name="uq_weekview_versions_business_key",
        ),
    )
    Table(
        "weekview_residents_count",
        metadata,
        _tenant_column(),
        _department_column(),
        _year_column(),
        _week_column(),
        _day_column(),
        _meal_column(),
        _count_column(),
        _updated_at_column(),
        UniqueConstraint(
            "tenant_id",
            "department_id",
            "year",
            "week",
            "day_of_week",
            "meal",
            name="uq_weekview_residents_count_business_key",
        ),
    )
    Table(
        "weekview_alt2_flags",
        metadata,
        _site_column(),
        _department_column(),
        _year_column(),
        _week_column(),
        _day_column(),
        _enabled_column(dialect),
        _updated_at_column(),
        UniqueConstraint(
            "site_id",
            "department_id",
            "year",
            "week",
            "day_of_week",
            name="uq_weekview_alt2_flags_business_key",
        ),
    )
    return metadata


def _tenant_column():
    return Column("tenant_id", Integer().with_variant(Text(), "sqlite"), nullable=False)


def _department_column():
    return Column("department_id", Text(), nullable=False)


def _site_column():
    return Column("site_id", Text(), nullable=False)


def _year_column():
    return Column("year", Integer(), nullable=False)


def _week_column():
    return Column("week", Integer(), nullable=False)


def _day_column():
    return Column("day_of_week", Integer(), nullable=False)


def _meal_column():
    return Column("meal", Text(), nullable=False)


def _diet_type_column():
    return Column("diet_type", Text(), nullable=False)


def _marked_column():
    return Column("marked", Integer(), nullable=False, server_default=text("0"))


def _count_column():
    return Column("count", Integer(), nullable=False, server_default=text("0"))


def _version_column():
    return Column("version", Integer(), nullable=False, server_default=text("0"))


def _enabled_column(dialect: str = "sqlite"):
    return Column(
        "enabled",
        Boolean().with_variant(Integer(), "sqlite"),
        nullable=False,
        server_default=text("FALSE" if dialect == "postgresql" else "0"),
    )


def _updated_at_column():
    return Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


def _normalized_default(default) -> str:
    value = str(default).strip().lower()
    while value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    return value.replace("::text", "").replace("::integer", "").replace("::boolean", "")


def _valid_default(column_name: str, default, dialect: str) -> bool:
    normalized = _normalized_default(default)
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


def _has_conflict_key(inspector, table_name: str, unique_columns: tuple[str, ...]) -> bool:
    primary_key = tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
    if primary_key == unique_columns:
        return True
    uniques = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint.get("column_names")
    }
    uniques.update(
        tuple(index["column_names"])
        for index in inspector.get_indexes(table_name)
        if index.get("unique")
        and index.get("column_names")
        and not any(
            index.get("dialect_options", {}).get(key) is not None
            for key in ("sqlite_where", "postgresql_where")
        )
    )
    return unique_columns in uniques


def ensure_weekview_schema(connection) -> None:
    """Provision and verify the canonical Weekview schema for an explicit bootstrap."""
    metadata = _metadata(connection.dialect.name)
    metadata.create_all(connection, checkfirst=True)
    verify_weekview_schema(connection)


def verify_weekview_schema(connection) -> None:
    try:
        _verify_weekview_schema(connection)
    except WeekviewSchemaError:
        raise
    except SQLAlchemyError as exc:
        raise WeekviewSchemaError("Weekview schema inspection failed") from exc


def _verify_weekview_schema(connection) -> None:
    """Reject missing or incompatible Weekview structures without repairing data."""
    from sqlalchemy import inspect

    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    missing = set(WEEKVIEW_TABLES) - table_names
    if missing:
        raise WeekviewSchemaError("Weekview schema incomplete: required table missing")

    contracts = {
        "weekview_registrations": (
            {"tenant_id", "department_id", "year", "week", "day_of_week", "meal", "diet_type", "marked", "updated_at"},
            ("tenant_id", "department_id", "year", "week", "day_of_week", "meal", "diet_type"),
        ),
        "weekview_versions": (
            {"tenant_id", "department_id", "year", "week", "version", "updated_at"},
            ("tenant_id", "department_id", "year", "week"),
        ),
        "weekview_residents_count": (
            {"tenant_id", "department_id", "year", "week", "day_of_week", "meal", "count", "updated_at"},
            ("tenant_id", "department_id", "year", "week", "day_of_week", "meal"),
        ),
        "weekview_alt2_flags": (
            {"site_id", "department_id", "year", "week", "day_of_week", "enabled", "updated_at"},
            ("site_id", "department_id", "year", "week", "day_of_week"),
        ),
    }
    for table_name, (required_columns, unique_columns) in contracts.items():
        column_info = {
            column["name"]: column for column in inspector.get_columns(table_name)
        }
        columns = set(column_info)
        if not required_columns.issubset(columns):
            raise WeekviewSchemaError("Weekview schema incompatible: required column missing")
        legacy_columns = (
            {"tenant_id", "is_alt2"}
            if table_name == "weekview_alt2_flags"
            else set()
        )
        if legacy_columns.intersection(columns):
            raise WeekviewSchemaError("Weekview schema incompatible: legacy columns present")
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
        for column_name in required_columns:
            type_name = str(column_info[column_name]["type"]).upper()
            if column_name == "tenant_id":
                valid = (
                    "INT" in type_name
                    if connection.dialect.name == "postgresql"
                    else any(marker in type_name for marker in ("INT", "CHAR", "TEXT", "CLOB"))
                )
            elif column_name == "enabled" and connection.dialect.name == "postgresql":
                valid = "BOOL" in type_name
            else:
                valid = "INT" in type_name
            if column_name in integer_columns and not valid:
                raise WeekviewSchemaError("Weekview schema incompatible: column type mismatch")
            if column_name in text_columns and not any(
                marker in type_name for marker in ("CHAR", "TEXT", "CLOB")
            ):
                raise WeekviewSchemaError("Weekview schema incompatible: column type mismatch")
            if column_name == "updated_at" and not any(
                marker in type_name for marker in ("DATE", "TIME")
            ):
                raise WeekviewSchemaError("Weekview schema incompatible: column type mismatch")
            if column_info[column_name].get("nullable", True):
                raise WeekviewSchemaError("Weekview schema incompatible: nullable required column")
            if column_name in {"marked", "count", "version", "enabled", "updated_at"}:
                default = column_info[column_name].get("default")
                if default is None or not _valid_default(
                    column_name, default, connection.dialect.name
                ):
                    raise WeekviewSchemaError("Weekview schema incompatible: invalid required default")
        for column_name, info in column_info.items():
            if column_name not in required_columns and not info.get("nullable", True) and info.get("default") is None:
                raise WeekviewSchemaError("Weekview schema incompatible: unsupported required column")
        if not _has_conflict_key(inspector, table_name, unique_columns):
            raise WeekviewSchemaError("Weekview schema incompatible: required unique key missing")
