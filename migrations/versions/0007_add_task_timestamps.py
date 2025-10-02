"""Add created_at and updated_at to tasks

Revision ID: 0007_add_task_timestamps
Revises: 0006_merge_heads
Create Date: 2025-09-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0007_add_task_timestamps"
down_revision = "0006_merge_heads"
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    cols = {c["name"] for c in insp.get_columns("tasks")}
    # SQLite cannot add column with non-constant default CURRENT_TIMESTAMP in some modes.
    # Strategy: add nullable columns without default, backfill manually.
    if "created_at" not in cols:
        op.add_column("tasks", sa.Column("created_at", sa.DateTime(), nullable=True))
    if "updated_at" not in cols:
        op.add_column("tasks", sa.Column("updated_at", sa.DateTime(), nullable=True))
    # Backfill both columns with current timestamp if null
    conn.execute(text("UPDATE tasks SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
    # (Optional) We leave them nullable to keep migration simple across SQLite; 
    # application code always sets values on create/update.


def downgrade() -> None:
    # Safe to drop (non-breaking for earlier code paths)
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
