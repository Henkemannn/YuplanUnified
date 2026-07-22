"""Add Offshore v2 prep tasks table

Revision ID: 0029_add_offshore_v2_prep_tasks
Revises: 0028_add_offshore_v2_menu_context
Create Date: 2026-07-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0029_add_offshore_v2_prep_tasks"
down_revision = "0028_add_offshore_v2_menu_context"
branch_labels = None
depends_on = None


def _table_exists(inspector, name: str) -> bool:
    try:
        return name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if _table_exists(inspector, "offshore_prep_tasks"):
        return

    op.create_table(
        "offshore_prep_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("work_period_id", sa.Integer(), nullable=False),
        sa.Column("service_event_id", sa.Integer(), nullable=False),
        sa.Column("builder_component_id", sa.String(length=128), nullable=True),
        sa.Column("component_name_snapshot", sa.String(length=240), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("planned_time", sa.Time(), nullable=True),
        sa.Column("work_position_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'planned'")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("completed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_prep_tasks_tenant_id"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_prep_tasks_site_id"),
        sa.ForeignKeyConstraint(["work_period_id"], ["offshore_work_periods.id"], name="fk_offshore_prep_tasks_work_period_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_event_id"], ["offshore_service_events.id"], name="fk_offshore_prep_tasks_service_event_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_position_id"], ["offshore_work_positions.id"], name="fk_offshore_prep_tasks_work_position_id"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_offshore_prep_tasks_created_by_user_id"),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], name="fk_offshore_prep_tasks_completed_by_user_id"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_offshore_prep_tasks_title_not_empty"),
        sa.CheckConstraint("sort_order >= 0", name="ck_offshore_prep_tasks_sort_order_nonnegative"),
        sa.CheckConstraint("lower(status) IN ('planned', 'in_progress', 'completed', 'cancelled')", name="ck_offshore_prep_tasks_status_allowed"),
    )

    for idx_name, cols in [
        ("ix_offshore_prep_tasks_tenant_site_date_status", ["tenant_id", "site_id", "planned_date", "status", "sort_order"]),
        ("ix_offshore_prep_tasks_service_event_sort", ["service_event_id", "sort_order"]),
        ("ix_offshore_prep_tasks_work_period_date", ["work_period_id", "planned_date"]),
        ("ix_offshore_prep_tasks_work_position", ["work_position_id"]),
    ]:
        try:
            op.create_index(idx_name, "offshore_prep_tasks", cols, unique=False)
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    for idx_name in [
        "ix_offshore_prep_tasks_work_position",
        "ix_offshore_prep_tasks_work_period_date",
        "ix_offshore_prep_tasks_service_event_sort",
        "ix_offshore_prep_tasks_tenant_site_date_status",
    ]:
        try:
            op.drop_index(idx_name, table_name="offshore_prep_tasks")
        except Exception:
            pass

    if _table_exists(inspector, "offshore_prep_tasks"):
        op.drop_table("offshore_prep_tasks")
