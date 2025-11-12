"""Initial schema

Revision ID: 0001_init
Revises: 
Create Date: 2025-09-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else "sqlite"
    true_def = sa.text("TRUE") if dialect == "postgresql" else sa.text("1")
    false_def = sa.text("FALSE") if dialect == "postgresql" else sa.text("0")
    active_default = true_def
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=active_default),
    )
    op.create_table("units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("default_attendance", sa.Integer())
    )
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"))
    )
    op.create_table("dishes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50))
    )
    op.create_table("recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text())
    )
    op.create_table("menus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id","week","year", name="uq_menu_tenant_year_week")
    )
    op.create_table("menu_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("menu_id", sa.Integer(), sa.ForeignKey("menus.id"), nullable=False),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("meal", sa.String(length=20), nullable=False),
        sa.Column("variant_type", sa.String(length=20), nullable=False),
        sa.Column("dish_id", sa.Integer(), sa.ForeignKey("dishes.id")),
        sa.UniqueConstraint("menu_id","day","meal","variant_type", name="uq_menu_variant_slot")
    )
    op.create_table("menu_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("meal", sa.String(length=20), nullable=False),
        sa.Column("variant_type", sa.String(length=20), nullable=False),
        sa.Column("replacement_dish_id", sa.Integer(), sa.ForeignKey("dishes.id")),
        sa.Column("scope", sa.String(length=20), nullable=False)
    )
    op.create_table("dietary_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("default_select", sa.Boolean(), server_default=false_def)
    )
    op.create_table("unit_diet_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("dietary_type_id", sa.Integer(), sa.ForeignKey("dietary_types.id"), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0")),
        sa.UniqueConstraint("unit_id","dietary_type_id", name="uq_unit_diet_assignment")
    )
    op.create_table("attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("meal", sa.String(length=20), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=20)),
        sa.UniqueConstraint("unit_id","date","meal", name="uq_attendance_unit_date_meal")
    )
    op.create_table("shift_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("pattern_type", sa.String(length=40), nullable=False)
    )
    op.create_table("shift_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("shift_templates.id")),
        sa.Column("start_ts", sa.DateTime(), nullable=False),
        sa.Column("end_ts", sa.DateTime(), nullable=False),
        sa.Column("role", sa.String(length=80)),
        sa.Column("status", sa.String(length=20), server_default="planned"),
        sa.Column("notes", sa.Text())
    )
    op.create_table("tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("task_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("done", sa.Boolean(), server_default=false_def)
    )
    op.create_table("messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("audience_type", sa.String(length=30), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"))
    )
    op.create_table("tenant_feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=true_def, nullable=False),
        sa.UniqueConstraint("tenant_id","name", name="uq_tenant_feature")
    )
    op.create_table("portion_guidelines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id")),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("baseline_g_per_guest", sa.Integer()),
        sa.Column("protein_per_100g", sa.Float())
    )
    op.create_table("service_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("meal", sa.String(length=20), nullable=False),
        sa.Column("dish_id", sa.Integer(), sa.ForeignKey("dishes.id")),
        sa.Column("category", sa.String(length=50)),
        sa.Column("guest_count", sa.Integer()),
        sa.Column("produced_qty_kg", sa.Float()),
        sa.Column("served_qty_kg", sa.Float()),
        sa.Column("leftover_qty_kg", sa.Float()),
        sa.Column("served_g_per_guest", sa.Float())
    )

    # Indices (selected)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_menu_variants_lookup", "menu_variants", ["menu_id", "day", "meal", "variant_type"])
    op.create_index("ix_shift_slots_time", "shift_slots", ["tenant_id", "start_ts"])
    op.create_index("ix_service_metrics_date", "service_metrics", ["tenant_id", "date"])
    # Additional constraints and indexes (merged from former 0002 for SQLite compatibility)
    op.create_index("ix_menu_overrides_tenant_date", "menu_overrides", ["tenant_id", "date"])
    op.create_index("ix_attendance_unit_date", "attendance", ["unit_id", "date"])
    op.create_index("ix_tasks_tenant_done", "tasks", ["tenant_id", "done"])
    op.create_index("ix_messages_tenant_created", "messages", ["tenant_id", "created_at"])


def downgrade() -> None:
    # Drop added indexes / constraints first (reverse order safe)
    op.drop_index("ix_messages_tenant_created", table_name="messages")
    op.drop_index("ix_tasks_tenant_done", table_name="tasks")
    op.drop_index("ix_attendance_unit_date", table_name="attendance")
    op.drop_index("ix_menu_overrides_tenant_date", table_name="menu_overrides")
    op.drop_constraint("uq_unit_diet_assignment", "unit_diet_assignments", type_="unique")
    op.drop_constraint("uq_attendance_unit_date_meal", "attendance", type_="unique")
    op.drop_constraint("uq_menu_variant_slot", "menu_variants", type_="unique")
    op.drop_constraint("uq_menu_tenant_year_week", "menus", type_="unique")
    op.drop_table("service_metrics")
    op.drop_table("portion_guidelines")
    op.drop_table("messages")
    op.drop_table("tenant_feature_flags")
    op.drop_table("tasks")
    op.drop_table("shift_slots")
    op.drop_table("shift_templates")
    op.drop_table("attendance")
    op.drop_table("unit_diet_assignments")
    op.drop_table("dietary_types")
    op.drop_table("menu_overrides")
    op.drop_table("menu_variants")
    op.drop_table("menus")
    op.drop_table("recipes")
    op.drop_table("dishes")
    op.drop_table("users")
    op.drop_table("units")
    op.drop_table("tenants")
