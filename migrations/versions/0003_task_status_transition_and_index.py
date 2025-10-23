"""Add tasks.status index and task status transition audit table

Revision ID: 0003_task_status_transition_and_index
Revises: 0002_add_task_status
Create Date: 2025-09-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers
revision = "0003_task_status_transition_and_index"
down_revision = "0002_add_task_status"
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    # Ensure tasks.status index exists
    existing_task_idx = {ix["name"] for ix in insp.get_indexes("tasks")}
    if "ix_tasks_status" not in existing_task_idx:
        try:
            op.create_index("ix_tasks_status", "tasks", ["status"])
        except Exception:
            pass
    # Create transition table only if missing
    if "task_status_transitions" not in insp.get_table_names():
        op.create_table(
            "task_status_transitions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_status", sa.String(length=20)),
            sa.Column("to_status", sa.String(length=20), nullable=False),
            sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("changed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    # Ensure index on transitions exists
    existing_tr_idx = {ix["name"] for ix in insp.get_indexes("task_status_transitions")}
    if "ix_task_status_transitions_task" not in existing_tr_idx and "task_status_transitions" in insp.get_table_names():
        try:
            op.create_index("ix_task_status_transitions_task", "task_status_transitions", ["task_id", "changed_at"])
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index("ix_task_status_transitions_task", table_name="task_status_transitions")
    op.drop_table("task_status_transitions")
    op.drop_index("ix_tasks_status", table_name="tasks")
