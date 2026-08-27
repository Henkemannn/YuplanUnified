"""Add users.department_id

Revision ID: 0033_add_users_department_id
Revises: 0032_add_department_menu_choices
Create Date: 2026-08-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0033_add_users_department_id"
down_revision = "0032_add_department_menu_choices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "users" not in table_names:
        return

    cols = {str(col["name"]) for col in inspector.get_columns("users")}
    if "department_id" in cols:
        return

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key("fk_users_department_id", "departments", ["department_id"], ["id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "users" not in table_names:
        return

    cols = {str(col["name"]) for col in inspector.get_columns("users")}
    if "department_id" not in cols:
        return

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_users_department_id", type_="foreignkey")
        batch_op.drop_column("department_id")