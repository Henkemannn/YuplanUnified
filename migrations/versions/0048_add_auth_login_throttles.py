"""Add persistent login throttling rows.

Revision ID: 0048_add_auth_login_throttles
Revises: 0047_add_service_addon_scope_quantity_mode
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0048_add_auth_login_throttles"
down_revision = "0047_add_service_addon_scope_quantity_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_login_throttles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("in_flight_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("window_started_at", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("scope IN ('account', 'ip')", name="ck_auth_login_throttles_scope"),
        sa.CheckConstraint("failure_count >= 0", name="ck_auth_login_throttles_failure_count"),
        sa.CheckConstraint("in_flight_count >= 0", name="ck_auth_login_throttles_in_flight_count"),
        sa.UniqueConstraint("scope", "key_hash", name="uq_auth_login_throttles_scope_key"),
    )
    op.create_index(
        "ix_auth_login_throttles_locked_until",
        "auth_login_throttles",
        ["locked_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_login_throttles_locked_until", table_name="auth_login_throttles")
    op.drop_table("auth_login_throttles")
