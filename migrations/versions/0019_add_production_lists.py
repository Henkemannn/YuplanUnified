"""Add production lists table

Revision ID: 0019_add_production_lists
Revises: 0018_add_service_addons
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0019_add_production_lists"
down_revision = "0018_add_service_addons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "production_lists" not in table_names:
        op.create_table(
            "production_lists",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("site_id", sa.Text(), nullable=False),
            sa.Column("created_at", sa.Text(), nullable=True),
            sa.Column("date", sa.Text(), nullable=False),
            sa.Column("meal_type", sa.Text(), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "production_lists" in table_names:
        op.drop_table("production_lists")
