"""Add immutable commun builder publication revisions

Revision ID: 0043_add_commun_builder_publication_revisions
Revises: 0042_add_department_portal_week_submissions
Create Date: 2026-10-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision = "0043_add_commun_builder_publication_revisions"
down_revision = "0042_add_department_portal_week_submissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "commun_builder_publication_revisions" not in table_names:
        op.create_table(
            "commun_builder_publication_revisions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("week", sa.Integer(), nullable=False),
            sa.Column("legacy_menu_id", sa.Integer(), nullable=True),
            sa.Column("builder_menu_id", sa.String(length=64), nullable=False),
            sa.Column("builder_menu_version", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=24), nullable=False),
            sa.Column("projection_snapshot_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_commun_builder_publication_revisions_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_commun_builder_publication_revisions_site_id"),
            sa.ForeignKeyConstraint(["legacy_menu_id"], ["menus.id"], name="fk_commun_builder_publication_revisions_legacy_menu_id", ondelete="SET NULL"),
            sa.UniqueConstraint(
                "tenant_id",
                "site_id",
                "year",
                "week",
                "builder_menu_id",
                "builder_menu_version",
                name="uq_commun_builder_publication_revisions_business_key",
            ),
            sa.CheckConstraint("year > 0", name="ck_commun_builder_publication_revisions_year_positive"),
            sa.CheckConstraint("week BETWEEN 1 AND 53", name="ck_commun_builder_publication_revisions_week_range"),
            sa.CheckConstraint("length(trim(builder_menu_id)) > 0", name="ck_commun_builder_publication_revisions_builder_menu_id_not_empty"),
            sa.CheckConstraint("builder_menu_version > 0", name="ck_commun_builder_publication_revisions_builder_menu_version_positive"),
            sa.CheckConstraint("lower(source) IN ('manual', 'import', 'migration', 'pilot')", name="ck_commun_builder_publication_revisions_source_allowed"),
        )
        op.create_index(
            "ix_commun_builder_publication_revisions_site_year_week",
            "commun_builder_publication_revisions",
            ["site_id", "year", "week"],
        )
        op.create_index(
            "ix_commun_builder_publication_revisions_builder_menu",
            "commun_builder_publication_revisions",
            ["builder_menu_id", "builder_menu_version"],
        )

    columns = {col["name"] for col in inspector.get_columns("commun_builder_publication_pins")} if "commun_builder_publication_pins" in table_names else set()
    if "commun_builder_publication_pins" in table_names and "projection_snapshot_json" in columns:
        conn.execute(
            text(
                """
                INSERT INTO commun_builder_publication_revisions (
                    tenant_id, site_id, year, week, legacy_menu_id,
                    builder_menu_id, builder_menu_version, source,
                    projection_snapshot_json, created_at, updated_at
                )
                SELECT
                    tenant_id, site_id, year, week, legacy_menu_id,
                    builder_menu_id, builder_menu_version, source,
                    projection_snapshot_json, created_at, updated_at
                FROM commun_builder_publication_pins
                WHERE projection_snapshot_json IS NOT NULL
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "commun_builder_publication_revisions" in table_names:
        op.drop_index("ix_commun_builder_publication_revisions_builder_menu", table_name="commun_builder_publication_revisions")
        op.drop_index("ix_commun_builder_publication_revisions_site_year_week", table_name="commun_builder_publication_revisions")
        op.drop_table("commun_builder_publication_revisions")
