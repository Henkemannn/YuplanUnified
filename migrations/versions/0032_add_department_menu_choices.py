"""Add department menu choice table

Revision ID: 0032_add_department_menu_choices
Revises: 0031_add_commun_builder_publication_snapshot
Create Date: 2026-08-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0032_add_department_menu_choices"
down_revision = "0031_add_commun_builder_publication_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "department_menu_choices" in table_names:
        return

    op.create_table(
        "department_menu_choices",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("meal", sa.String(length=20), nullable=False, server_default=sa.text("'lunch'")),
        sa.Column("selected_variant", sa.String(length=8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_department_menu_choices_tenant_id"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_department_menu_choices_site_id"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_department_menu_choices_department_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "site_id",
            "department_id",
            "year",
            "week",
            "weekday",
            "meal",
            name="uq_department_menu_choices_business_key",
        ),
        sa.CheckConstraint("year > 0", name="ck_department_menu_choices_year_positive"),
        sa.CheckConstraint("week BETWEEN 1 AND 53", name="ck_department_menu_choices_week_range"),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_department_menu_choices_weekday_range"),
        sa.CheckConstraint("length(trim(selected_variant)) > 0", name="ck_department_menu_choices_selected_variant_not_empty"),
        sa.CheckConstraint("lower(selected_variant) IN ('alt1', 'alt2')", name="ck_department_menu_choices_selected_variant_allowed"),
        sa.CheckConstraint("lower(meal) = 'lunch'", name="ck_department_menu_choices_meal_lunch_only"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "department_menu_choices" in table_names:
        op.drop_table("department_menu_choices")