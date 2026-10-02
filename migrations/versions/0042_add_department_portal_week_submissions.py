"""Add department portal week submissions

Revision ID: 0042_add_department_portal_week_submissions
Revises: 0041_add_department_requirement_group_completions
Create Date: 2026-10-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0042_add_department_portal_week_submissions"
down_revision = "0041_add_department_requirement_group_completions"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    table_names = _table_names()

    if "department_portal_week_submissions" not in table_names:
        op.create_table(
            "department_portal_week_submissions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("department_id", sa.String(length=64), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("week", sa.Integer(), nullable=False),
            sa.Column("builder_menu_id", sa.String(length=64), nullable=False),
            sa.Column("builder_menu_version", sa.Integer(), nullable=False),
            sa.Column("choice_signature", sa.String(length=64), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_department_portal_week_submissions_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_department_portal_week_submissions_site_id"),
            sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_department_portal_week_submissions_department_id"),
            sa.UniqueConstraint(
                "tenant_id",
                "site_id",
                "department_id",
                "year",
                "week",
                name="uq_department_portal_week_submissions_business_key",
            ),
            sa.CheckConstraint("year > 0", name="ck_department_portal_week_submissions_year_positive"),
            sa.CheckConstraint("week BETWEEN 1 AND 53", name="ck_department_portal_week_submissions_week_range"),
            sa.CheckConstraint(
                "length(trim(builder_menu_id)) > 0",
                name="ck_department_portal_week_submissions_builder_menu_id_not_empty",
            ),
            sa.CheckConstraint(
                "builder_menu_version > 0",
                name="ck_department_portal_week_submissions_builder_menu_version_positive",
            ),
            sa.CheckConstraint(
                "length(trim(choice_signature)) > 0",
                name="ck_department_portal_week_submissions_choice_signature_not_empty",
            ),
        )


def downgrade() -> None:
    table_names = _table_names()

    if "department_portal_week_submissions" in table_names:
        op.drop_table("department_portal_week_submissions")