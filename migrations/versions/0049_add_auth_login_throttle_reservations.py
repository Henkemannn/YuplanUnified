"""Add expiring, single-use login attempt reservations.

Revision ID: 0049_add_auth_login_throttle_reservations
Revises: 0048_add_auth_login_throttles
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0049_add_auth_login_throttle_reservations"
down_revision = "0048_add_auth_login_throttles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_login_throttle_reservations",
        sa.Column("reservation_hash", sa.String(length=64), primary_key=True),
        sa.Column("account_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_auth_login_throttle_reservations_expires_at",
        "auth_login_throttle_reservations",
        ["expires_at"],
    )
    op.create_index(
        "ix_auth_login_throttle_reservations_account_hash",
        "auth_login_throttle_reservations",
        ["account_hash"],
    )
    op.create_index(
        "ix_auth_login_throttle_reservations_ip_hash",
        "auth_login_throttle_reservations",
        ["ip_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_login_throttle_reservations_ip_hash",
        table_name="auth_login_throttle_reservations",
    )
    op.drop_index(
        "ix_auth_login_throttle_reservations_account_hash",
        table_name="auth_login_throttle_reservations",
    )
    op.drop_index(
        "ix_auth_login_throttle_reservations_expires_at",
        table_name="auth_login_throttle_reservations",
    )
    op.drop_table("auth_login_throttle_reservations")
