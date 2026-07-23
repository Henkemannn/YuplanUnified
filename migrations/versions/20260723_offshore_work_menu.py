"""offshore work menu decisions

Revision ID: 20260723_offshore_work_menu
Revises: 0029_add_offshore_v2_prep_tasks
Create Date: 2026-07-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260723_offshore_work_menu"
down_revision = "0029_add_offshore_v2_prep_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offshore_installation_settings", sa.Column("menu_track_visibility_json", sa.Text(), nullable=True))
    op.create_table(
        "offshore_work_menu_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.String(length=64), nullable=False),
        sa.Column("service_event_id", sa.Integer(), nullable=False),
        sa.Column("menu_track_key", sa.String(length=64), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("selected_builder_composition_id", sa.String(length=128), nullable=True),
        sa.Column("free_text", sa.String(length=240), nullable=True),
        sa.Column("source_publication_pin_id", sa.String(length=36), nullable=True),
        sa.Column("source_publication_year", sa.Integer(), nullable=False),
        sa.Column("source_publication_week", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["service_event_id"], ["offshore_service_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["source_publication_pin_id"], ["commun_builder_publication_pins.id"], ondelete="SET NULL"),
        sa.CheckConstraint("length(trim(menu_track_key)) > 0", name="ck_offshore_work_menu_decisions_menu_track_key_not_empty"),
        sa.CheckConstraint("lower(decision_type) IN ('use_published', 'use_builder_composition', 'use_free_text')", name="ck_offshore_work_menu_decisions_decision_type_allowed"),
        sa.CheckConstraint("source_publication_year > 0", name="ck_offshore_work_menu_decisions_publication_year_positive"),
        sa.CheckConstraint("source_publication_week BETWEEN 1 AND 53", name="ck_offshore_work_menu_decisions_publication_week_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "site_id", "service_event_id", "menu_track_key", name="uq_offshore_work_menu_decisions_event_track"),
    )
    op.create_index("ix_offshore_work_menu_decisions_tenant_site_event", "offshore_work_menu_decisions", ["tenant_id", "site_id", "service_event_id"], unique=False)
    op.create_index("ix_offshore_work_menu_decisions_tenant_site_track", "offshore_work_menu_decisions", ["tenant_id", "site_id", "menu_track_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_offshore_work_menu_decisions_tenant_site_track", table_name="offshore_work_menu_decisions")
    op.drop_index("ix_offshore_work_menu_decisions_tenant_site_event", table_name="offshore_work_menu_decisions")
    op.drop_table("offshore_work_menu_decisions")
    op.drop_column("offshore_installation_settings", "menu_track_visibility_json")