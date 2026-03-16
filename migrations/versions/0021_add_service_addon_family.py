"""Add addon_family to service_addons

Revision ID: 0021_add_service_addon_family
Revises: 0020_add_diet_family_to_dietary_types
Create Date: 2026-03-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0021_add_service_addon_family"
down_revision = "0020_add_diet_family_to_dietary_types"
branch_labels = None
depends_on = None


ALLOWED = ("mos", "sallad", "ovrigt")


def _normalize(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw == "ovritgt":
        raw = "ovrigt"
    if raw in ALLOWED:
        return raw
    return "ovrigt"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "service_addons" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("service_addons")}
    if "addon_family" not in columns:
        op.add_column("service_addons", sa.Column("addon_family", sa.String(length=32), nullable=True))

    rows = conn.execute(sa.text("SELECT id, addon_family FROM service_addons")).fetchall()
    for row in rows:
        family = _normalize(str(row[1] or ""))
        conn.execute(
            sa.text("UPDATE service_addons SET addon_family=:f WHERE id=:id"),
            {"f": family, "id": str(row[0])},
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "service_addons" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("service_addons")}
    if "addon_family" not in columns:
        return

    if conn.dialect.name == "sqlite":
        # Keep column on sqlite downgrade to avoid table rebuild complexity.
        return

    op.drop_column("service_addons", "addon_family")
