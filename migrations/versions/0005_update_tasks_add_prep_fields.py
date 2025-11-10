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

    menu_missing = "menu_id" not in cols
    dish_missing = "dish_id" not in cols
    private_missing = "private_flag" not in cols
    assignee_missing = "assignee_id" not in cols
    creator_missing = "creator_user_id" not in cols

    if any([menu_missing, dish_missing, private_missing, assignee_missing, creator_missing]):
        with op.batch_alter_table("tasks") as batch:
            # Add columns without FK inline constraints to avoid unnamed constraint errors in batch mode
            if menu_missing:
                batch.add_column(sa.Column("menu_id", sa.Integer(), nullable=True))
            if dish_missing:
                batch.add_column(sa.Column("dish_id", sa.Integer(), nullable=True))
            if private_missing:
                batch.add_column(sa.Column("private_flag", sa.Boolean(), server_default=sa.text("0"), nullable=False))
            if assignee_missing:
                batch.add_column(sa.Column("assignee_id", sa.Integer(), nullable=True))
            if creator_missing:
                batch.add_column(sa.Column("creator_user_id", sa.Integer(), nullable=True))

            # Create named foreign keys explicitly (SQLite batch mode requires named constraints)
            if menu_missing:
                batch.create_foreign_key(
                    "fk_tasks_menu_id_menus",
                    referent_table="menus",
                    local_cols=["menu_id"],
                    remote_cols=["id"],
                )
            if dish_missing:
                batch.create_foreign_key(
                    "fk_tasks_dish_id_dishes",
                    referent_table="dishes",
                    local_cols=["dish_id"],
                    remote_cols=["id"],
                )
            if assignee_missing:
                batch.create_foreign_key(
                    "fk_tasks_assignee_id_users",
                    referent_table="users",
                    local_cols=["assignee_id"],
                    remote_cols=["id"],
                )
            if creator_missing:
                batch.create_foreign_key(
                    "fk_tasks_creator_user_id_users",
                    referent_table="users",
                    local_cols=["creator_user_id"],
                    remote_cols=["id"],
                )

    # Index
    existing_idx = {ix["name"] for ix in inspector.get_indexes("tasks")}
    if "ix_tasks_tenant_done_private" not in existing_idx:
        try:
            op.create_index("ix_tasks_tenant_done_private", "tasks", ["tenant_id", "done", "private_flag"])
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
