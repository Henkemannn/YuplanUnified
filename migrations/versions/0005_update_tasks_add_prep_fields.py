"""Add prep task fields to tasks

Revision ID: 0005_update_tasks_add_prep_fields
Revises: 0004_add_notes
Create Date: 2025-09-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0005_update_tasks_add_prep_fields"
down_revision = "0004_add_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("tasks")}
    # Build list of columns to add (WITHOUT ForeignKey inline constraints to avoid unnamed constraints in batch mode)
    to_add: list[sa.Column] = []
    new_fk_cols: list[str] = []
    if "menu_id" not in cols:
        to_add.append(sa.Column("menu_id", sa.Integer()))
        new_fk_cols.append("menu_id")
    if "dish_id" not in cols:
        to_add.append(sa.Column("dish_id", sa.Integer()))
        new_fk_cols.append("dish_id")
    if "private_flag" not in cols:
        to_add.append(sa.Column("private_flag", sa.Boolean(), server_default=sa.text("0"), nullable=False))
    if "assignee_id" not in cols:
        to_add.append(sa.Column("assignee_id", sa.Integer()))
        new_fk_cols.append("assignee_id")
    if "creator_user_id" not in cols:
        to_add.append(sa.Column("creator_user_id", sa.Integer()))
        new_fk_cols.append("creator_user_id")

    if to_add:
        with op.batch_alter_table("tasks") as batch:
            for col in to_add:
                batch.add_column(col)
            # Create named foreign keys for newly added FK columns
            existing_fks = {tuple(fk.get("constrained_columns", [])) for fk in inspector.get_foreign_keys("tasks")}
            if "menu_id" in new_fk_cols and ("menu_id",) not in existing_fks:
                batch.create_foreign_key(
                    "fk_tasks_menu_id_menus", "menus", ["menu_id"], ["id"], ondelete=None
                )
            if "dish_id" in new_fk_cols and ("dish_id",) not in existing_fks:
                batch.create_foreign_key(
                    "fk_tasks_dish_id_dishes", "dishes", ["dish_id"], ["id"], ondelete=None
                )
            if "assignee_id" in new_fk_cols and ("assignee_id",) not in existing_fks:
                batch.create_foreign_key(
                    "fk_tasks_assignee_id_users", "users", ["assignee_id"], ["id"], ondelete=None
                )
            if "creator_user_id" in new_fk_cols and ("creator_user_id",) not in existing_fks:
                batch.create_foreign_key(
                    "fk_tasks_creator_user_id_users", "users", ["creator_user_id"], ["id"], ondelete=None
                )
    # Index
    existing_idx = {ix["name"] for ix in inspector.get_indexes("tasks")}
    if "ix_tasks_tenant_done_private" not in existing_idx:
        try:
            op.create_index("ix_tasks_tenant_done_private", "tasks", ["tenant_id","done","private_flag"])
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index("ix_tasks_tenant_done_private", table_name="tasks")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("creator_user_id")
        batch.drop_column("assignee_id")
        batch.drop_column("private_flag")
        batch.drop_column("dish_id")
        batch.drop_column("menu_id")
