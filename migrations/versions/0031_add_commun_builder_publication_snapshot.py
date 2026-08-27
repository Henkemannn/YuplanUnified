"""Add durable snapshot payload to commun builder publication pins

Revision ID: 0031_add_commun_builder_publication_snapshot
Revises: 0030_add_offshore_work_menu_owner_scope
Create Date: 2026-08-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0031_add_commun_builder_publication_snapshot"
down_revision = "0030_add_offshore_work_menu_owner_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "commun_builder_publication_pins" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("commun_builder_publication_pins")}
    if "projection_snapshot_json" in columns:
        return

    op.add_column(
        "commun_builder_publication_pins",
        sa.Column("projection_snapshot_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "commun_builder_publication_pins" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("commun_builder_publication_pins")}
    if "projection_snapshot_json" not in columns:
        return

    op.drop_column("commun_builder_publication_pins", "projection_snapshot_json")
