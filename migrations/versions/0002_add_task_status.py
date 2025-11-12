"""Add status column to tasks and backfill

Revision ID: 0002_add_task_status
Revises: 0001_init
Create Date: 2025-09-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_add_task_status"
down_revision = "0001_init"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add nullable first for wide compatibility
    op.add_column("tasks", sa.Column("status", sa.String(length=20), nullable=True))
    # Backfill using done flag: done -> done else todo
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else "sqlite"
    if dialect == "postgresql":
        conn.execute(sa.text("UPDATE tasks SET status = CASE WHEN done IS TRUE THEN 'done' ELSE 'todo' END"))
    else:
        conn.execute(sa.text("UPDATE tasks SET status = CASE WHEN done = 1 THEN 'done' ELSE 'todo' END"))
    # Set any remaining NULL (shouldn't be) to todo
    conn.execute(sa.text("UPDATE tasks SET status = 'todo' WHERE status IS NULL"))
    # (Optionally) could alter to non-null, but keep nullable to avoid dialect-specific issues


def downgrade() -> None:
    op.drop_column("tasks", "status")
