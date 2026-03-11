"""Add department_diet_overrides table

Revision ID: 0017_add_department_diet_overrides
Revises: 0016_add_department_display_order
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0017_add_department_diet_overrides"
down_revision = "0016_add_department_display_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "department_diet_overrides" not in table_names:
        op.create_table(
            "department_diet_overrides",
            sa.Column("department_id", sa.String(length=64), nullable=False),
            sa.Column("diet_type_id", sa.String(length=64), nullable=False),
            sa.Column("day", sa.Integer(), nullable=False),
            sa.Column("meal", sa.String(length=16), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("department_id", "diet_type_id", "day", "meal"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "department_diet_overrides" in table_names:
        op.drop_table("department_diet_overrides")
