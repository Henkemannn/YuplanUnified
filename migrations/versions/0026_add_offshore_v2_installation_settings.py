"""Add Offshore v2 installation and menu cycle tables

Revision ID: 0026_add_offshore_v2_installation_settings
Revises: 0025_add_commun_builder_publication_pins
Create Date: 2026-07-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0026_add_offshore_v2_installation_settings"
down_revision = "0025_add_commun_builder_publication_pins"
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

    if not _table_exists(inspector, "offshore_installation_settings"):
        op.create_table(
            "offshore_installation_settings",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'Europe/Oslo'")),
            sa.Column("default_locale", sa.String(length=8), nullable=False, server_default=sa.text("'sv'")),
            sa.Column("default_theme", sa.String(length=16), nullable=False, server_default=sa.text("'system'")),
            sa.Column("default_portions", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_installation_settings_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_installation_settings_site_id"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_offshore_installation_settings_created_by_user_id"),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], name="fk_offshore_installation_settings_updated_by_user_id"),
            sa.UniqueConstraint("tenant_id", "site_id", name="uq_offshore_installation_settings_tenant_site"),
            sa.CheckConstraint("length(trim(timezone)) > 0", name="ck_offshore_installation_settings_timezone_not_empty"),
            sa.CheckConstraint("lower(default_locale) IN ('sv', 'no', 'en')", name="ck_offshore_installation_settings_locale_allowed"),
            sa.CheckConstraint("lower(default_theme) IN ('system', 'light', 'dark')", name="ck_offshore_installation_settings_theme_allowed"),
            sa.CheckConstraint("default_portions IS NULL OR default_portions BETWEEN 1 AND 10000", name="ck_offshore_installation_settings_default_portions_range"),
        )

    if not _table_exists(inspector, "offshore_work_positions"):
        op.create_table(
            "offshore_work_positions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("position_type", sa.String(length=20), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_work_positions_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_work_positions_site_id"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_offshore_work_positions_created_by_user_id"),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], name="fk_offshore_work_positions_updated_by_user_id"),
            sa.UniqueConstraint("tenant_id", "site_id", "code", name="uq_offshore_work_positions_tenant_site_code"),
            sa.CheckConstraint("length(trim(code)) > 0", name="ck_offshore_work_positions_code_not_empty"),
            sa.CheckConstraint("length(trim(name)) > 0", name="ck_offshore_work_positions_name_not_empty"),
            sa.CheckConstraint("lower(position_type) IN ('cook', 'lead', 'bakery', 'other')", name="ck_offshore_work_positions_position_type_allowed"),
        )

    if not _table_exists(inspector, "offshore_menu_cycles"):
        op.create_table(
            "offshore_menu_cycles",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("cycle_length", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_menu_cycles_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_menu_cycles_site_id"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_offshore_menu_cycles_created_by_user_id"),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], name="fk_offshore_menu_cycles_updated_by_user_id"),
            sa.CheckConstraint("length(trim(name)) > 0", name="ck_offshore_menu_cycles_name_not_empty"),
            sa.CheckConstraint("cycle_length BETWEEN 1 AND 52", name="ck_offshore_menu_cycles_cycle_length_range"),
        )

    if not _table_exists(inspector, "offshore_menu_cycle_slots"):
        op.create_table(
            "offshore_menu_cycle_slots",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.String(length=64), nullable=False),
            sa.Column("menu_cycle_id", sa.Integer(), nullable=False),
            sa.Column("cycle_index", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_offshore_menu_cycle_slots_tenant_id"),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name="fk_offshore_menu_cycle_slots_site_id"),
            sa.ForeignKeyConstraint(["menu_cycle_id"], ["offshore_menu_cycles.id"], name="fk_offshore_menu_cycle_slots_menu_cycle_id", ondelete="CASCADE"),
            sa.UniqueConstraint("menu_cycle_id", "cycle_index", name="uq_offshore_menu_cycle_slots_cycle_index"),
            sa.CheckConstraint("cycle_index >= 1", name="ck_offshore_menu_cycle_slots_cycle_index_positive"),
            sa.CheckConstraint("length(trim(label)) > 0", name="ck_offshore_menu_cycle_slots_label_not_empty"),
        )

    try:
        op.create_index("ix_offshore_installation_settings_tenant_site", "offshore_installation_settings", ["tenant_id", "site_id"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("ix_offshore_work_positions_tenant_site_sort", "offshore_work_positions", ["tenant_id", "site_id", "sort_order"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("ix_offshore_work_positions_tenant_site_active", "offshore_work_positions", ["tenant_id", "site_id", "is_active"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("ix_offshore_menu_cycles_tenant_site_active", "offshore_menu_cycles", ["tenant_id", "site_id", "is_active"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("ix_offshore_menu_cycles_tenant_site_name", "offshore_menu_cycles", ["tenant_id", "site_id", "name"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("ix_offshore_menu_cycle_slots_cycle_sort", "offshore_menu_cycle_slots", ["menu_cycle_id", "sort_order"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("ix_offshore_menu_cycle_slots_tenant_site", "offshore_menu_cycle_slots", ["tenant_id", "site_id"], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    for idx, table in [
        ("ix_offshore_menu_cycle_slots_tenant_site", "offshore_menu_cycle_slots"),
        ("ix_offshore_menu_cycle_slots_cycle_sort", "offshore_menu_cycle_slots"),
        ("ix_offshore_menu_cycles_tenant_site_name", "offshore_menu_cycles"),
        ("ix_offshore_menu_cycles_tenant_site_active", "offshore_menu_cycles"),
        ("ix_offshore_work_positions_tenant_site_active", "offshore_work_positions"),
        ("ix_offshore_work_positions_tenant_site_sort", "offshore_work_positions"),
        ("ix_offshore_installation_settings_tenant_site", "offshore_installation_settings"),
    ]:
        try:
            op.drop_index(idx, table_name=table)
        except Exception:
            pass

    for table in [
        "offshore_menu_cycle_slots",
        "offshore_menu_cycles",
        "offshore_work_positions",
        "offshore_installation_settings",
    ]:
        try:
            if _table_exists(inspector, table):
                op.drop_table(table)
        except Exception:
            pass