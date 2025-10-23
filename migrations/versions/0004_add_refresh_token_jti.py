"""Add refresh_token_jti column to users

Revision ID: 0004_add_refresh_token_jti
Revises: 0003_task_status_transition_and_index
Create Date: 2025-09-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004_add_refresh_token_jti"
down_revision = "0003_task_status_transition_and_index"
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "refresh_token_jti" not in cols:
        op.add_column("users", sa.Column("refresh_token_jti", sa.String(length=64), nullable=True))
    existing_idx = {ix["name"] for ix in insp.get_indexes("users")}
    if "ix_users_refresh_jti" not in existing_idx:
        try:
            op.create_index("ix_users_refresh_jti", "users", ["refresh_token_jti"])
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index("ix_users_refresh_jti", table_name="users")
    op.drop_column("users", "refresh_token_jti")
