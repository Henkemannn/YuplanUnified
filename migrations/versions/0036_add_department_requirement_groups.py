"""Add department requirement groups

Revision ID: 0036_add_department_requirement_groups
Revises: 0035_add_dietary_types_requirement_identity
Create Date: 2026-09-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0036_add_department_requirement_groups"
down_revision = "0035_add_dietary_types_requirement_identity"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    table_names = _table_names()

    if "department_requirement_groups" not in table_names:
        op.create_table(
            "department_requirement_groups",
            sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
            sa.Column("department_id", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=True),
            sa.Column("default_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(
                ["department_id"],
                ["departments.id"],
                name="fk_department_requirement_groups_department_id",
                ondelete="CASCADE",
            ),
            sa.CheckConstraint(
                "default_quantity >= 0",
                name="ck_department_requirement_groups_default_quantity_non_negative",
            ),
            sa.CheckConstraint(
                "is_active IN (0, 1)",
                name="ck_department_requirement_groups_is_active_bool",
            ),
        )
        op.create_index(
            "ix_department_requirement_groups_department_id",
            "department_requirement_groups",
            ["department_id"],
        )

    if "department_requirement_group_requirements" not in table_names:
        op.create_table(
            "department_requirement_group_requirements",
            sa.Column("group_id", sa.String(length=64), nullable=False),
            sa.Column("dietary_type_id", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("group_id", "dietary_type_id", name="pk_department_requirement_group_requirements"),
            sa.ForeignKeyConstraint(
                ["group_id"],
                ["department_requirement_groups.id"],
                name="fk_department_requirement_group_requirements_group_id",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["dietary_type_id"],
                ["dietary_types.id"],
                name="fk_department_requirement_group_requirements_dietary_type_id",
            ),
        )
        op.create_index(
            "ix_department_requirement_group_requirements_dietary_type_id",
            "department_requirement_group_requirements",
            ["dietary_type_id"],
        )


def downgrade() -> None:
    table_names = _table_names()

    if "department_requirement_group_requirements" in table_names:
        op.drop_table("department_requirement_group_requirements")

    if "department_requirement_groups" in table_names:
        op.drop_index("ix_department_requirement_groups_department_id", table_name="department_requirement_groups")
        op.drop_table("department_requirement_groups")
