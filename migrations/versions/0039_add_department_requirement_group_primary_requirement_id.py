"""Add primary requirement to department requirement groups

Revision ID: 0039_add_department_requirement_group_primary_requirement_id
Revises: 0038_add_planning_option_reviews
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision = "0039_add_department_requirement_group_primary_requirement_id"
down_revision = "0038_add_planning_option_reviews"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _backfill(conn) -> None:
    conn.execute(
        text(
            """
            UPDATE department_requirement_groups
            SET primary_requirement_id = (
                SELECT gr.dietary_type_id
                FROM department_requirement_group_requirements gr
                WHERE gr.group_id = department_requirement_groups.id
            )
            WHERE (
                SELECT COUNT(*)
                FROM department_requirement_group_requirements gr
                WHERE gr.group_id = department_requirement_groups.id
            ) = 1
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE department_requirement_groups
            SET primary_requirement_id = NULL
            WHERE (
                SELECT COUNT(*)
                FROM department_requirement_group_requirements gr
                WHERE gr.group_id = department_requirement_groups.id
            ) <> 1
            """
        )
    )


def upgrade() -> None:
    table_names = _table_names()
    if "department_requirement_groups" not in table_names:
        return

    columns = _column_names("department_requirement_groups")
    if "primary_requirement_id" not in columns:
        with op.batch_alter_table(
            "department_requirement_groups",
            recreate="always",
            reflect_kwargs={"resolve_fks": False},
        ) as batch_op:
            batch_op.add_column(sa.Column("primary_requirement_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_department_requirement_groups_primary_requirement_id",
                "dietary_types",
                ["primary_requirement_id"],
                ["id"],
            )

    _backfill(op.get_bind())


def downgrade() -> None:
    table_names = _table_names()
    if "department_requirement_groups" not in table_names:
        return

    columns = _column_names("department_requirement_groups")
    if "primary_requirement_id" in columns:
        with op.batch_alter_table(
            "department_requirement_groups",
            recreate="always",
            reflect_kwargs={"resolve_fks": False},
        ) as batch_op:
            batch_op.drop_constraint(
                "fk_department_requirement_groups_primary_requirement_id",
                type_="foreignkey",
            )
            batch_op.drop_column("primary_requirement_id")