"""Add Offshore v2 service-event menu context table

Revision ID: 0028_add_offshore_v2_menu_context
Revises: 0027_add_offshore_v2_periods
Create Date: 2026-07-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0028_add_offshore_v2_menu_context"
down_revision = "0027_add_offshore_v2_periods"
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

    if "offshore_work_periods" in inspector.get_table_names():
        with op.batch_alter_table("offshore_work_periods") as batch_op:
            try:
                batch_op.add_column(sa.Column("start_menu_cycle_slot_id", sa.Integer(), nullable=True))
            except Exception:
                pass
            try:
                batch_op.create_foreign_key(
                    "fk_offshore_work_periods_start_menu_cycle_slot_id",
                    "offshore_menu_cycle_slots",
                    ["start_menu_cycle_slot_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass

    if _table_exists(inspector, "offshore_service_event_menu_contexts"):
        return

    op.create_table(
        "offshore_service_event_menu_contexts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("work_period_id", sa.Integer(), nullable=False),
        sa.Column("service_event_id", sa.Integer(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("menu_cycle_id", sa.Integer(), nullable=True),
        sa.Column("start_menu_cycle_slot_id", sa.Integer(), nullable=True),
        sa.Column("menu_cycle_slot_id", sa.Integer(), nullable=True),
        sa.Column("menu_cycle_index", sa.Integer(), nullable=True),
        sa.Column("service_key", sa.String(length=80), nullable=True),
        sa.Column("resolution_status", sa.String(length=20), nullable=False),
        sa.Column("assignment_source", sa.String(length=20), nullable=False),
        sa.Column("match_status", sa.String(length=20), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("manual_note", sa.Text(), nullable=True),
        sa.Column("builder_publication_pin_id", sa.String(length=64), nullable=True),
        sa.Column("builder_publication_year", sa.Integer(), nullable=False),
        sa.Column("builder_publication_week", sa.Integer(), nullable=False),
        sa.Column("builder_menu_id", sa.String(length=64), nullable=True),
        sa.Column("builder_menu_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_service_event_menu_contexts_tenant_id"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_service_event_menu_contexts_site_id"),
        sa.ForeignKeyConstraint(["work_period_id"], ["offshore_work_periods.id"], name="fk_offshore_service_event_menu_contexts_work_period_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_event_id"], ["offshore_service_events.id"], name="fk_offshore_service_event_menu_contexts_service_event_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["menu_cycle_id"], ["offshore_menu_cycles.id"], name="fk_offshore_service_event_menu_contexts_menu_cycle_id"),
        sa.ForeignKeyConstraint(["start_menu_cycle_slot_id"], ["offshore_menu_cycle_slots.id"], name="fk_offshore_service_event_menu_contexts_start_menu_cycle_slot_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["menu_cycle_slot_id"], ["offshore_menu_cycle_slots.id"], name="fk_offshore_service_event_menu_contexts_menu_cycle_slot_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["builder_publication_pin_id"], ["commun_builder_publication_pins.id"], name="fk_offshore_service_event_menu_contexts_builder_publication_pin_id", ondelete="SET NULL"),
        sa.UniqueConstraint("service_event_id", name="uq_offshore_service_event_menu_contexts_service_event_id"),
        sa.CheckConstraint("builder_publication_year > 0", name="ck_offshore_service_event_menu_contexts_publication_year_positive"),
        sa.CheckConstraint("builder_publication_week BETWEEN 1 AND 53", name="ck_offshore_service_event_menu_contexts_publication_week_range"),
        sa.CheckConstraint("menu_cycle_index IS NULL OR menu_cycle_index > 0", name="ck_offshore_service_event_menu_contexts_cycle_index_positive"),
        sa.CheckConstraint("builder_menu_version IS NULL OR builder_menu_version > 0", name="ck_offshore_service_event_menu_contexts_builder_menu_version_positive"),
        sa.CheckConstraint("lower(resolution_status) IN ('resolved', 'unresolved', 'unavailable', 'manual')", name="ck_offshore_service_event_menu_contexts_resolution_status_allowed"),
        sa.CheckConstraint("lower(assignment_source) IN ('automatic', 'manual')", name="ck_offshore_service_event_menu_contexts_assignment_source_allowed"),
        sa.CheckConstraint("match_status IS NULL OR lower(match_status) IN ('matched', 'missing', 'ambiguous', 'withdrawn')", name="ck_offshore_service_event_menu_contexts_match_status_allowed"),
    )

    for idx_name, cols in [
        ("ix_offshore_service_event_menu_contexts_tenant_site_date", ["tenant_id", "site_id", "service_date"]),
        ("ix_offshore_service_event_menu_contexts_work_period", ["work_period_id", "service_date"]),
        ("ix_offshore_service_event_menu_contexts_tenant_site_status", ["tenant_id", "site_id", "resolution_status"]),
    ]:
        try:
            op.create_index(idx_name, "offshore_service_event_menu_contexts", cols, unique=False)
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if "offshore_work_periods" in inspector.get_table_names():
        with op.batch_alter_table("offshore_work_periods") as batch_op:
            try:
                batch_op.drop_constraint("fk_offshore_work_periods_start_menu_cycle_slot_id", type_="foreignkey")
            except Exception:
                pass
            try:
                batch_op.drop_column("start_menu_cycle_slot_id")
            except Exception:
                pass

    for idx_name in [
        "ix_offshore_service_event_menu_contexts_tenant_site_status",
        "ix_offshore_service_event_menu_contexts_work_period",
        "ix_offshore_service_event_menu_contexts_tenant_site_date",
    ]:
        try:
            op.drop_index(idx_name, table_name="offshore_service_event_menu_contexts")
        except Exception:
            pass

    if _table_exists(inspector, "offshore_service_event_menu_contexts"):
        op.drop_table("offshore_service_event_menu_contexts")