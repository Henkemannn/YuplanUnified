"""add users.updated_at

Revision ID: 778407d29f47
Revises: 0012_add_user_fields
Create Date: 2026-01-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "778407d29f47"
down_revision = "0012_add_user_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode to be safe on SQLite and generally across dialects when constraints exist.
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=True,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_column("updated_at")
