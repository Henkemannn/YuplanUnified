"""Scope new generic Notes to an explicit site.

Revision ID: 0052_add_site_id_to_notes
Revises: 0051_add_site_scoped_menu_uniqueness
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0052_add_site_id_to_notes"
down_revision = "0051_add_site_scoped_menu_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notes", recreate="always") as batch:
        batch.add_column(sa.Column("site_id", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_notes_site_id",
            "sites",
            ["site_id"],
            ["id"],
        )
    op.create_index(
        "ix_notes_tenant_site",
        "notes",
        ["tenant_id", "site_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notes_tenant_site", table_name="notes")
    with op.batch_alter_table("notes", recreate="always") as batch:
        batch.drop_constraint("fk_notes_site_id", type_="foreignkey")
        batch.drop_column("site_id")
