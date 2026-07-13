"""Add commun builder publication pin table

Revision ID: 0025_add_commun_builder_publication_pins
Revises: 0024_add_commun_builder_menu_links
Create Date: 2026-07-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0025_add_commun_builder_publication_pins"
down_revision = "0024_add_commun_builder_menu_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "commun_builder_publication_pins" in table_names:
        return

    op.create_table(
        "commun_builder_publication_pins",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("legacy_menu_id", sa.Integer(), nullable=True),
        sa.Column("builder_menu_id", sa.String(length=64), nullable=False),
        sa.Column("builder_menu_version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_commun_builder_publication_pins_tenant_id"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_commun_builder_publication_pins_site_id"),
        sa.ForeignKeyConstraint(
            ["legacy_menu_id"],
            ["menus.id"],
            name="fk_commun_builder_publication_pins_legacy_menu_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "site_id",
            "year",
            "week",
            name="uq_commun_builder_publication_pins_tenant_site_year_week",
        ),
        sa.CheckConstraint("year > 0", name="ck_commun_builder_publication_pins_year_positive"),
        sa.CheckConstraint("week BETWEEN 1 AND 53", name="ck_commun_builder_publication_pins_week_range"),
        sa.CheckConstraint(
            "length(trim(builder_menu_id)) > 0",
            name="ck_commun_builder_publication_pins_builder_menu_id_not_empty",
        ),
        sa.CheckConstraint(
            "builder_menu_version > 0",
            name="ck_commun_builder_publication_pins_builder_menu_version_positive",
        ),
        sa.CheckConstraint(
            "lower(source) IN ('manual', 'import', 'migration', 'pilot')",
            name="ck_commun_builder_publication_pins_source_allowed",
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "commun_builder_publication_pins" in table_names:
        op.drop_table("commun_builder_publication_pins")
