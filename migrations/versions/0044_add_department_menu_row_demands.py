"""Add department menu row demand table

Revision ID: 0044_add_department_menu_row_demands
Revises: 0043_add_commun_builder_publication_revisions
Create Date: 2026-10-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0044_add_department_menu_row_demands"
down_revision = "0043_add_commun_builder_publication_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "department_menu_row_demands",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("builder_menu_id", sa.String(length=64), nullable=False),
        sa.Column("builder_menu_version", sa.Integer(), nullable=False),
        sa.Column("builder_menu_row_id", sa.String(length=64), nullable=False),
        sa.Column("selection_group_id", sa.String(length=64), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_department_menu_row_demands_tenant_id"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_department_menu_row_demands_site_id"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_department_menu_row_demands_department_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "site_id",
            "department_id",
            "year",
            "week",
            "weekday",
            "builder_menu_id",
            "builder_menu_version",
            "builder_menu_row_id",
            name="uq_department_menu_row_demands_business_key",
        ),
        sa.CheckConstraint("year > 0", name="ck_department_menu_row_demands_year_positive"),
        sa.CheckConstraint("week BETWEEN 1 AND 53", name="ck_department_menu_row_demands_week_range"),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_department_menu_row_demands_weekday_range"),
        sa.CheckConstraint("length(trim(builder_menu_id)) > 0", name="ck_department_menu_row_demands_builder_menu_id_not_empty"),
        sa.CheckConstraint("builder_menu_version > 0", name="ck_department_menu_row_demands_builder_menu_version_positive"),
        sa.CheckConstraint("length(trim(builder_menu_row_id)) > 0", name="ck_department_menu_row_demands_builder_menu_row_id_not_empty"),
        sa.CheckConstraint("quantity >= 0", name="ck_department_menu_row_demands_quantity_non_negative"),
    )
    op.create_index(
        "ix_department_menu_row_demands_department_id",
        "department_menu_row_demands",
        ["department_id"],
    )
    op.create_index(
        "ix_department_menu_row_demands_builder_menu_row_id",
        "department_menu_row_demands",
        ["builder_menu_row_id"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "department_menu_row_demands" in table_names:
        op.drop_index("ix_department_menu_row_demands_builder_menu_row_id", table_name="department_menu_row_demands")
        op.drop_index("ix_department_menu_row_demands_department_id", table_name="department_menu_row_demands")
        op.drop_table("department_menu_row_demands")
