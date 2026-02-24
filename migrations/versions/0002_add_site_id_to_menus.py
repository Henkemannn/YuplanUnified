"""Add site_id to menus

Revision ID: 0002_add_site_id_to_menus
Revises: 0001_init
Create Date: 2026-02-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_add_site_id_to_menus"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("menus", sa.Column("site_id", sa.Text(), nullable=True))
    op.create_index(
        "ix_menus_tenant_site_week",
        "menus",
        ["tenant_id", "site_id", "year", "week"],
    )
    op.execute(
        """
        UPDATE menus
        SET site_id = (
          SELECT MIN(s.id) FROM sites s WHERE s.tenant_id = menus.tenant_id
        )
        WHERE site_id IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_menus_tenant_site_week", table_name="menus")
    op.drop_column("menus", "site_id")
