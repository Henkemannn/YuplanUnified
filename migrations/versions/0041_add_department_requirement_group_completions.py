"""Add department requirement group completions

Revision ID: 0041_add_department_requirement_group_completions
Revises: 0040_add_department_requirement_group_weekday_overrides
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0041_add_department_requirement_group_completions"
down_revision = "0040_add_department_requirement_group_weekday_overrides"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    table_names = _table_names()

    if "department_requirement_group_completions" not in table_names:
        op.create_table(
            "department_requirement_group_completions",
            sa.Column("group_id", sa.String(length=64), nullable=False),
            sa.Column("service_date", sa.Date(), nullable=False),
            sa.Column("meal_key", sa.String(length=64), nullable=False),
            sa.Column("marked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.ForeignKeyConstraint(
                ["group_id"],
                ["department_requirement_groups.id"],
                name="fk_department_requirement_group_completions_group_id",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("group_id", "service_date", "meal_key", name="pk_department_requirement_group_completions"),
            sa.CheckConstraint(
                "length(trim(meal_key)) > 0",
                name="ck_department_requirement_group_completions_meal_key_not_empty",
            ),
            sa.CheckConstraint(
                "meal_key = lower(trim(meal_key))",
                name="ck_department_requirement_group_completions_meal_key_normalized",
            ),
            sa.CheckConstraint(
                "meal_key IN ('lunch', 'dinner')",
                name="ck_department_requirement_group_completions_meal_key_allowed",
            ),
        )


def downgrade() -> None:
    table_names = _table_names()

    if "department_requirement_group_completions" in table_names:
        op.drop_table("department_requirement_group_completions")