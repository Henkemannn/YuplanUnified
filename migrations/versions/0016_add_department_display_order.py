"""Add display_order to departments

Revision ID: 0016_add_department_display_order
Revises: 0015_merge_all_heads
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0016_add_department_display_order"
down_revision = "0015_merge_all_heads"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    try:
        cols = inspector.get_columns(table_name)
        return any(c.get("name") == column_name for c in cols)
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "departments" in table_names and not _has_column(inspector, "departments", "display_order"):
        op.add_column("departments", sa.Column("display_order", sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "departments" in table_names and _has_column(inspector, "departments", "display_order"):
        op.drop_column("departments", "display_order")
