"""Add planning option reviews

Revision ID: 0038_add_planning_option_reviews
Revises: 0037_add_department_requirement_group_service_overrides
Create Date: 2026-09-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0038_add_planning_option_reviews"
down_revision = "0037_add_department_requirement_group_service_overrides"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    table_names = _table_names()

    if "planning_option_reviews" not in table_names:
        op.create_table(
            "planning_option_reviews",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("service_date", sa.Date(), nullable=False),
            sa.Column("meal", sa.String(length=20), nullable=False),
            sa.Column("builder_menu_id", sa.String(length=64), nullable=False),
            sa.Column("builder_menu_version", sa.Integer(), nullable=False),
            sa.Column("builder_menu_row_id", sa.String(length=64), nullable=False),
            sa.Column("review_basis_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("review_basis_hash", sa.String(length=64), nullable=False),
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_planning_option_reviews_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_planning_option_reviews_site_id"),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], name="fk_planning_option_reviews_reviewed_by_user_id"),
            sa.UniqueConstraint(
                "tenant_id",
                "site_id",
                "service_date",
                "meal",
                "builder_menu_id",
                "builder_menu_version",
                "builder_menu_row_id",
                name="uq_planning_option_reviews_scope",
            ),
            sa.CheckConstraint(
                "length(trim(builder_menu_id)) > 0",
                name="ck_planning_option_reviews_builder_menu_id_not_empty",
            ),
            sa.CheckConstraint(
                "builder_menu_version > 0",
                name="ck_planning_option_reviews_builder_menu_version_positive",
            ),
            sa.CheckConstraint(
                "length(trim(builder_menu_row_id)) > 0",
                name="ck_planning_option_reviews_builder_menu_row_id_not_empty",
            ),
            sa.CheckConstraint(
                "review_basis_version > 0",
                name="ck_planning_option_reviews_review_basis_version_positive",
            ),
        )
        op.create_index(
            "ix_planning_option_reviews_tenant_scope",
            "planning_option_reviews",
            ["tenant_id", "site_id", "service_date", "meal"],
        )
        op.create_index(
            "ix_planning_option_reviews_tenant_row",
            "planning_option_reviews",
            ["tenant_id", "builder_menu_row_id"],
        )

    if "planning_option_review_decisions" not in table_names:
        op.create_table(
            "planning_option_review_decisions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("review_id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("destination_id", sa.String(length=64), nullable=False),
            sa.Column("requirement_group_id", sa.String(length=64), nullable=False),
            sa.Column("decision", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(
                ["review_id"],
                ["planning_option_reviews.id"],
                name="fk_planning_option_review_decisions_review_id",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_planning_option_review_decisions_tenant_id"),
            sa.ForeignKeyConstraint(["destination_id"], ["departments.id"], name="fk_planning_option_review_decisions_destination_id"),
            sa.ForeignKeyConstraint(
                ["requirement_group_id"],
                ["department_requirement_groups.id"],
                name="fk_planning_option_review_decisions_requirement_group_id",
            ),
            sa.UniqueConstraint(
                "review_id",
                "destination_id",
                "requirement_group_id",
                name="uq_planning_option_review_decisions_scope",
            ),
            sa.CheckConstraint(
                "decision IN ('NO_ADAPTATION_REQUIRED', 'ADAPTATION_REQUIRED')",
                name="ck_planning_option_review_decisions_decision_allowed",
            ),
        )
        op.create_index(
            "ix_planning_option_review_decisions_tenant_review",
            "planning_option_review_decisions",
            ["tenant_id", "review_id"],
        )
        op.create_index(
            "ix_planning_option_review_decisions_tenant_destination",
            "planning_option_review_decisions",
            ["tenant_id", "destination_id"],
        )


def downgrade() -> None:
    table_names = _table_names()

    if "planning_option_review_decisions" in table_names:
        op.drop_index("ix_planning_option_review_decisions_tenant_destination", table_name="planning_option_review_decisions")
        op.drop_index("ix_planning_option_review_decisions_tenant_review", table_name="planning_option_review_decisions")
        op.drop_table("planning_option_review_decisions")

    if "planning_option_reviews" in table_names:
        op.drop_index("ix_planning_option_reviews_tenant_row", table_name="planning_option_reviews")
        op.drop_index("ix_planning_option_reviews_tenant_scope", table_name="planning_option_reviews")
        op.drop_table("planning_option_reviews")
