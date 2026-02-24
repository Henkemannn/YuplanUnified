"""Add remember_to_order_items table

Revision ID: 0013_add_remember_to_order_items
Revises: 0012_add_user_fields
Create Date: 2026-02-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0013_add_remember_to_order_items"
down_revision = "0012_add_user_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    now_default = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "remember_to_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("week_key", sa.String(length=10), nullable=False),
        sa.Column("text", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_role", sa.String(length=20), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_remember_to_order_items_site_week_checked",
        "remember_to_order_items",
        ["site_id", "week_key", "checked_at"],
    )

    if dialect == "sqlite":
        # SQLite does not enforce FK on users/sites in this project; no extra actions needed.
        pass


def downgrade() -> None:
    op.drop_index("ix_remember_to_order_items_site_week_checked", table_name="remember_to_order_items")
    op.drop_table("remember_to_order_items")
