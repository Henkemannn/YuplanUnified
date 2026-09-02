"""Add department requirement group service overrides

Revision ID: 0037_add_department_requirement_group_service_overrides
Revises: 0036_add_department_requirement_groups
Create Date: 2026-09-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0037_add_department_requirement_group_service_overrides"
down_revision = "0036_add_department_requirement_groups"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    table_names = _table_names()

    if "department_requirement_group_service_overrides" not in table_names:
        op.create_table(
            "department_requirement_group_service_overrides",
            sa.Column("group_id", sa.String(length=64), nullable=False),
            sa.Column("service_date", sa.Date(), nullable=False),
            sa.Column("meal_key", sa.String(length=64), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("group_id", "service_date", "meal_key", name="pk_department_requirement_group_service_overrides"),
            sa.ForeignKeyConstraint(
                ["group_id"],
                ["department_requirement_groups.id"],
                name="fk_department_requirement_group_service_overrides_group_id",
                ondelete="CASCADE",
            ),
            sa.CheckConstraint(
                "quantity >= 0",
                name="ck_department_requirement_group_service_overrides_quantity_non_negative",
            ),
            sa.CheckConstraint(
                "length(trim(meal_key)) > 0",
                name="ck_department_requirement_group_service_overrides_meal_key_not_empty",
            ),
            sa.CheckConstraint(
                "meal_key = lower(trim(meal_key))",
                name="ck_department_requirement_group_service_overrides_meal_key_normalized",
            ),
        )


def downgrade() -> None:
    table_names = _table_names()

    if "department_requirement_group_service_overrides" in table_names:
        op.drop_table("department_requirement_group_service_overrides")