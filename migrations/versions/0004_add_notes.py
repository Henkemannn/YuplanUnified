"""Add notes table

Revision ID: 0004_add_notes
Revises: 0003_tenant_feature_flags
Create Date: 2025-09-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0004_add_notes"
down_revision = "0003_tenant_feature_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    if "notes" not in existing_tables:
        op.create_table(
            "notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("private_flag", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )
    # Ensure index exists
    idx_names = {ix["name"] for ix in inspector.get_indexes("notes")} if "notes" in existing_tables else set()
    if "ix_notes_tenant_created" not in idx_names and "notes" in (existing_tables | {"notes"}):
        try:
            op.create_index("ix_notes_tenant_created", "notes", ["tenant_id", "created_at"])
        except Exception:
            pass  # ignore if racing or backend limitation


def downgrade() -> None:
    op.drop_index("ix_notes_tenant_created", table_name="notes")
    op.drop_table("notes")
