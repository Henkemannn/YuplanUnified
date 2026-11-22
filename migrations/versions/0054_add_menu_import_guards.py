"""Add durable menu import guards.

Revision ID: 0054_add_menu_import_guards
Revises: 0053_add_site_scope_to_dishes
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0054_add_menu_import_guards"
down_revision = "0053_add_site_scope_to_dishes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "menu_import_guards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("active_key", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'needs_review')",
            name="ck_menu_import_guards_status",
        ),
        sa.CheckConstraint("year > 0", name="ck_menu_import_guards_year_positive"),
        sa.CheckConstraint(
            "week BETWEEN 1 AND 53",
            name="ck_menu_import_guards_week_range",
        ),
        sa.UniqueConstraint(
            "operation_id",
            "year",
            "week",
            name="uq_menu_import_guards_operation_week",
        ),
        sa.UniqueConstraint("active_key", name="uq_menu_import_guards_active_key"),
    )
    op.create_index(
        "ix_menu_import_guards_operation_id",
        "menu_import_guards",
        ["operation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_menu_import_guards_operation_id", table_name="menu_import_guards")
    op.drop_table("menu_import_guards")
