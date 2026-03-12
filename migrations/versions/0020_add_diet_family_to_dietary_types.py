"""Add diet_family to dietary types with backfill

Revision ID: 0020_add_diet_family_to_dietary_types
Revises: 0019_add_production_lists
Create Date: 2026-03-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0020_add_diet_family_to_dietary_types"
down_revision = "0019_add_production_lists"
branch_labels = None
depends_on = None


def _infer_family(name: str | None) -> str:
    txt = str(name or "").strip().lower()
    if not txt:
        return "Övrigt"

    if any(k in txt for k in ("timbal", "pat", "flyt", "pure", "pate", "konsistens", "lattugg", "passerad")):
        return "Textur"
    if any(k in txt for k in ("vegetar", "vegan", "pesc", "halal", "kosher")):
        return "Kostval"
    if any(k in txt for k in ("gluten", "laktos", "mjolk", "fiskfri", "not", "nott", "agg", "soja", "utan ", "ej ", "allerg")):
        return "Allergi / Exkludering"
    if any(k in txt for k in ("energi", "protein", "berik", "diabet", "anpass")):
        return "Anpassning"
    return "Övrigt"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "dietary_types" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("dietary_types")}
    if "diet_family" not in columns:
        op.add_column("dietary_types", sa.Column("diet_family", sa.Text(), nullable=True))

    rows = conn.execute(sa.text("SELECT id, name, diet_family FROM dietary_types")).fetchall()
    for row in rows:
        existing = str(row[2] or "").strip()
        family = existing if existing else _infer_family(str(row[1] or ""))
        conn.execute(
            sa.text("UPDATE dietary_types SET diet_family=:family WHERE id=:id"),
            {"family": family, "id": int(row[0])},
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "dietary_types" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("dietary_types")}
    if "diet_family" not in columns:
        return

    if conn.dialect.name == "sqlite":
        # SQLite cannot reliably drop columns without table rebuild; keep column on downgrade.
        return

    op.drop_column("dietary_types", "diet_family")
