"""Add pilot activity events table

Revision ID: 0022_add_pilot_activity_events
Revises: 0021_add_service_addon_family
Create Date: 2026-03-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0022_add_pilot_activity_events"
down_revision = "0021_add_service_addon_family"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "pilot_activity_events" not in table_names:
        op.create_table(
            "pilot_activity_events",
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("site_id", sa.String(length=64), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    try:
        op.create_index(
            "idx_pilot_activity_site_created",
            "pilot_activity_events",
            ["site_id", "created_at"],
            unique=False,
        )
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "pilot_activity_events" in table_names:
        try:
            op.drop_index("idx_pilot_activity_site_created", table_name="pilot_activity_events")
        except Exception:
            pass
        op.drop_table("pilot_activity_events")
