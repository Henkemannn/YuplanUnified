"""Add auth_version to users

Revision ID: 0045_add_user_auth_version
Revises: 0044_add_department_menu_row_demands
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0045_add_user_auth_version"
down_revision = "0044_add_department_menu_row_demands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auth_version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_column("auth_version")
