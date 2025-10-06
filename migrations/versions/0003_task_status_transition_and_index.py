"""Add tasks.status index and task status transition audit table

Revision ID: 0003_task_status_transition_and_index
Revises: 0002_add_task_status
Create Date: 2025-09-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0003_task_status_transition_and_index"
down_revision = "0002_add_task_status"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_table("task_status_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(length=20)),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"))
    )
    op.create_index("ix_task_status_transitions_task", "task_status_transitions", ["task_id","changed_at"])


def downgrade() -> None:
    op.drop_index("ix_task_status_transitions_task", table_name="task_status_transitions")
    op.drop_table("task_status_transitions")
    op.drop_index("ix_tasks_status", table_name="tasks")
