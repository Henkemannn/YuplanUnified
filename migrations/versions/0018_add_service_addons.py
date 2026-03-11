"""Add service addons tables

Revision ID: 0018_add_service_addons
Revises: 0017_add_department_diet_overrides
Create Date: 2026-03-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0018_add_service_addons"
down_revision = "0017_add_department_diet_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "service_addons" not in table_names:
        op.create_table(
            "service_addons",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_service_addons_name"),
        )

    if "department_service_addons" not in table_names:
        op.create_table(
            "department_service_addons",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("department_id", sa.String(length=64), nullable=False),
            sa.Column("addon_id", sa.String(length=64), nullable=False),
            sa.Column("lunch_count", sa.Integer(), nullable=True),
            sa.Column("dinner_count", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "department_service_addons" in table_names:
        op.drop_table("department_service_addons")
    if "service_addons" in table_names:
        op.drop_table("service_addons")
