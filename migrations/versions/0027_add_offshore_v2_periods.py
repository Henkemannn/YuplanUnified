"""Add Offshore v2 period templates and work periods

Revision ID: 0027_add_offshore_v2_periods
Revises: 0026_add_offshore_v2_installation_settings
Create Date: 2026-07-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0027_add_offshore_v2_periods"
down_revision = "0026_add_offshore_v2_installation_settings"
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

    if not _table_exists(inspector, "offshore_period_templates"):
        op.create_table(
            "offshore_period_templates",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("duration_days", sa.Integer(), nullable=False),
            sa.Column("start_weekday", sa.Integer(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_period_templates_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_period_templates_site_id"),
            sa.UniqueConstraint("tenant_id", "site_id", "name", "active", name="uq_offshore_period_templates_tenant_site_name_active"),
            sa.CheckConstraint("length(trim(name)) > 0", name="ck_offshore_period_templates_name_not_empty"),
            sa.CheckConstraint("duration_days >= 1", name="ck_offshore_period_templates_duration_positive"),
            sa.CheckConstraint("start_weekday IS NULL OR start_weekday BETWEEN 0 AND 6", name="ck_offshore_period_templates_start_weekday_range"),
        )

    if not _table_exists(inspector, "offshore_period_template_events"):
        op.create_table(
            "offshore_period_template_events",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("period_template_id", sa.Integer(), nullable=False),
            sa.Column("day_offset", sa.Integer(), nullable=False),
            sa.Column("local_time", sa.Time(), nullable=False),
            sa.Column("service_code", sa.String(length=80), nullable=False),
            sa.Column("display_name", sa.String(length=160), nullable=False),
            sa.Column("work_position_id", sa.Integer(), nullable=True),
            sa.Column("default_portions", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_period_template_events_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_period_template_events_site_id"),
            sa.ForeignKeyConstraint(["period_template_id"], ["offshore_period_templates.id"], name="fk_offshore_period_template_events_period_template_id", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["work_position_id"], ["offshore_work_positions.id"], name="fk_offshore_period_template_events_work_position_id"),
            sa.UniqueConstraint(
                "period_template_id",
                "day_offset",
                "local_time",
                "service_code",
                name="uq_offshore_period_template_events_template_day_time_code",
            ),
            sa.CheckConstraint("day_offset >= 0", name="ck_offshore_period_template_events_day_offset_nonnegative"),
            sa.CheckConstraint("length(trim(service_code)) > 0", name="ck_offshore_period_template_events_service_code_not_empty"),
            sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_offshore_period_template_events_display_name_not_empty"),
            sa.CheckConstraint("default_portions IS NULL OR default_portions >= 0", name="ck_offshore_period_template_events_default_portions_nonnegative"),
        )

    if not _table_exists(inspector, "offshore_work_periods"):
        op.create_table(
            "offshore_work_periods",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("period_template_id", sa.Integer(), nullable=True),
            sa.Column("menu_cycle_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_work_periods_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_work_periods_site_id"),
            sa.ForeignKeyConstraint(["period_template_id"], ["offshore_period_templates.id"], name="fk_offshore_work_periods_period_template_id"),
            sa.ForeignKeyConstraint(["menu_cycle_id"], ["offshore_menu_cycles.id"], name="fk_offshore_work_periods_menu_cycle_id"),
            sa.CheckConstraint("length(trim(name)) > 0", name="ck_offshore_work_periods_name_not_empty"),
            sa.CheckConstraint("starts_at < ends_at", name="ck_offshore_work_periods_starts_before_ends"),
            sa.CheckConstraint(
                "lower(status) IN ('draft', 'planned', 'active', 'completed', 'cancelled')",
                name="ck_offshore_work_periods_status_allowed",
            ),
        )

    if not _table_exists(inspector, "offshore_service_events"):
        op.create_table(
            "offshore_service_events",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("work_period_id", sa.Integer(), nullable=False),
            sa.Column("source_template_event_id", sa.Integer(), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("service_code", sa.String(length=80), nullable=False),
            sa.Column("display_name", sa.String(length=160), nullable=False),
            sa.Column("work_position_id", sa.Integer(), nullable=True),
            sa.Column("expected_portions", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_service_events_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_service_events_site_id"),
            sa.ForeignKeyConstraint(["work_period_id"], ["offshore_work_periods.id"], name="fk_offshore_service_events_work_period_id", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_template_event_id"], ["offshore_period_template_events.id"], name="fk_offshore_service_events_source_template_event_id"),
            sa.ForeignKeyConstraint(["work_position_id"], ["offshore_work_positions.id"], name="fk_offshore_service_events_work_position_id"),
            sa.UniqueConstraint("work_period_id", "source_template_event_id", name="uq_offshore_service_events_period_source_template"),
            sa.CheckConstraint("length(trim(service_code)) > 0", name="ck_offshore_service_events_service_code_not_empty"),
            sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_offshore_service_events_display_name_not_empty"),
            sa.CheckConstraint("expected_portions IS NULL OR expected_portions >= 0", name="ck_offshore_service_events_expected_portions_nonnegative"),
            sa.CheckConstraint(
                "lower(status) IN ('planned', 'confirmed', 'completed', 'cancelled')",
                name="ck_offshore_service_events_status_allowed",
            ),
        )

    for idx_name, table_name, cols in [
        ("ix_offshore_period_templates_tenant_site_active_sort", "offshore_period_templates", ["tenant_id", "site_id", "active", "sort_order"]),
        ("ix_offshore_period_templates_tenant_site_name", "offshore_period_templates", ["tenant_id", "site_id", "name"]),
        ("ix_offshore_period_template_events_template_sort", "offshore_period_template_events", ["period_template_id", "sort_order"]),
        ("ix_offshore_period_template_events_tenant_site", "offshore_period_template_events", ["tenant_id", "site_id"]),
        ("ix_offshore_work_periods_tenant_site_starts_at", "offshore_work_periods", ["tenant_id", "site_id", "starts_at"]),
        ("ix_offshore_work_periods_tenant_site_ends_at", "offshore_work_periods", ["tenant_id", "site_id", "ends_at"]),
        ("ix_offshore_work_periods_tenant_site_status", "offshore_work_periods", ["tenant_id", "site_id", "status"]),
        ("ix_offshore_service_events_work_period_starts_at", "offshore_service_events", ["work_period_id", "starts_at"]),
        ("ix_offshore_service_events_tenant_site_status", "offshore_service_events", ["tenant_id", "site_id", "status"]),
    ]:
        try:
            op.create_index(idx_name, table_name, cols, unique=False)
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    for idx, table in [
        ("ix_offshore_service_events_tenant_site_status", "offshore_service_events"),
        ("ix_offshore_service_events_work_period_starts_at", "offshore_service_events"),
        ("ix_offshore_work_periods_tenant_site_status", "offshore_work_periods"),
        ("ix_offshore_work_periods_tenant_site_ends_at", "offshore_work_periods"),
        ("ix_offshore_work_periods_tenant_site_starts_at", "offshore_work_periods"),
        ("ix_offshore_period_template_events_tenant_site", "offshore_period_template_events"),
        ("ix_offshore_period_template_events_template_sort", "offshore_period_template_events"),
        ("ix_offshore_period_templates_tenant_site_name", "offshore_period_templates"),
        ("ix_offshore_period_templates_tenant_site_active_sort", "offshore_period_templates"),
    ]:
        try:
            op.drop_index(idx, table_name=table)
        except Exception:
            pass

    for table in [
        "offshore_service_events",
        "offshore_work_periods",
        "offshore_period_template_events",
        "offshore_period_templates",
    ]:
        try:
            if _table_exists(inspector, table):
                op.drop_table(table)
        except Exception:
            pass
