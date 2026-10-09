"""Add must_change_password to users

Revision ID: 0046_add_user_must_change_password
Revises: 0045_add_user_auth_version
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0046_add_user_must_change_password"
down_revision = "0045_add_user_auth_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_column("must_change_password")
