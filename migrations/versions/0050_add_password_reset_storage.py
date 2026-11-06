"""Add password reset tokens and request throttles.

Revision ID: 0050_add_password_reset_storage
Revises: 0049_add_auth_login_throttle_reservations
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0050_add_password_reset_storage"
down_revision = "0049_add_auth_login_throttle_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_password_reset_tokens_user_active",
        "password_reset_tokens",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        ["expires_at"],
    )

    op.create_table(
        "password_reset_throttles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("window_started_at", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "scope IN ('account', 'ip')",
            name="ck_password_reset_throttles_scope",
        ),
        sa.CheckConstraint(
            "request_count >= 0",
            name="ck_password_reset_throttles_request_count",
        ),
        sa.UniqueConstraint(
            "scope",
            "key_hash",
            name="uq_password_reset_throttles_scope_key",
        ),
    )
    op.create_index(
        "ix_password_reset_throttles_locked_until",
        "password_reset_throttles",
        ["locked_until"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_throttles_locked_until",
        table_name="password_reset_throttles",
    )
    op.drop_table("password_reset_throttles")
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_active", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
