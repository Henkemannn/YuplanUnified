"""Add site_id to dietary_types

Revision ID: 0034_add_dietary_types_site_id
Revises: 0033_add_users_department_id
Create Date: 2026-09-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0034_add_dietary_types_site_id"
down_revision = "0033_add_users_department_id"
branch_labels = None
depends_on = None


def _table_columns(inspector, table_name: str) -> set[str]:
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _table_indexes(inspector, table_name: str) -> set[str]:
    try:
        return {str(index["name"]) for index in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def _has_equivalent_lookup_index(inspector, table_name: str, column_names: list[str]) -> bool:
    try:
        for index in inspector.get_indexes(table_name):
            if list(index.get("column_names") or []) == column_names:
                return True
    except Exception:
        return False
    return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "dietary_types" not in table_names:
        return

    columns = _table_columns(inspector, "dietary_types")
    if "site_id" not in columns:
        op.add_column("dietary_types", sa.Column("site_id", sa.String(length=64), nullable=True))

    indexes = _table_indexes(inspector, "dietary_types")
    if "idx_dietary_types_site_name" not in indexes and not _has_equivalent_lookup_index(
        inspector,
        "dietary_types",
        ["site_id", "name"],
    ):
        op.create_index(
            "idx_dietary_types_site_name",
            "dietary_types",
            ["site_id", "name"],
            unique=False,
        )


def downgrade() -> None:
    """Non-destructive downgrade.

    Historical runtime repair may already have created `site_id` and/or a lookup
    index before Alembic owned this schema. We intentionally leave both in place
    rather than guessing ownership and risking data-loss on rollback.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "dietary_types" not in table_names:
        return

    # Intentionally no-op: leave site_id and lookup indexes intact.