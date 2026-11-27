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
    column = sa.Column(
        "updated_at",
        sa.DateTime(timezone=False),
        nullable=True,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.add_column(column)
    else:
        op.add_column("users", column)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.drop_column("updated_at")
    else:
        op.drop_column("users", "updated_at")
