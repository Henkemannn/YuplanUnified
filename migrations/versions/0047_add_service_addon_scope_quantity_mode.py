"""Add service addon scope and quantity mode

Revision ID: 0047_add_service_addon_scope_quantity_mode
Revises: 0046_add_user_must_change_password
Create Date: 2026-10-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0047_add_service_addon_scope_quantity_mode"
down_revision = "0046_add_user_must_change_password"
branch_labels = None
depends_on = None


def _table_has_column(conn, table_name: str, column_name: str) -> bool:
    try:
        cols = conn.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
        return any(str(c[1]) == column_name for c in cols)
    except Exception:
        try:
            cols = inspect(conn).get_columns(table_name)
            return any(str(c["name"]) == column_name for c in cols)
        except Exception:
            return False


def _normalize_count(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _canonicalize_legacy_row(lunch_count, dinner_count):
    lunch_i = _normalize_count(lunch_count)
    dinner_i = _normalize_count(dinner_count)
    has_lunch = lunch_i is not None and lunch_i > 0
    has_dinner = dinner_i is not None and dinner_i > 0
    if has_lunch and has_dinner:
        return "all_services", "custom", lunch_i, dinner_i
    if has_lunch:
        return "lunch", "custom", lunch_i, None
    if has_dinner:
        return "dinner", "custom", None, dinner_i
    raise RuntimeError("department_service_addons row cannot be backfilled safely")


def _backfill_rows(conn) -> None:
    rows = conn.execute(
        sa.text(
            """
            SELECT id, lunch_count, dinner_count
            FROM department_service_addons
            ORDER BY id
            """
        )
    ).fetchall()
    for row in rows:
        service_scope, quantity_mode, lunch_count, dinner_count = _canonicalize_legacy_row(row[1], row[2])
        conn.execute(
            sa.text(
                """
                UPDATE department_service_addons
                SET service_scope=:service_scope,
                    quantity_mode=:quantity_mode,
                    lunch_count=:lunch_count,
                    dinner_count=:dinner_count
                WHERE id=:id
                """
            ),
            {
                "id": str(row[0]),
                "service_scope": service_scope,
                "quantity_mode": quantity_mode,
                "lunch_count": lunch_count,
                "dinner_count": dinner_count,
            },
        )


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "department_service_addons" not in table_names:
        return

    cols = {str(c["name"]) for c in inspector.get_columns("department_service_addons")}
    if "service_scope" not in cols:
        op.add_column("department_service_addons", sa.Column("service_scope", sa.Text(), nullable=True))
    if "quantity_mode" not in cols:
        op.add_column("department_service_addons", sa.Column("quantity_mode", sa.Text(), nullable=True))

    _backfill_rows(conn)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "department_service_addons" not in table_names:
        return

    cols = {str(c["name"]) for c in inspector.get_columns("department_service_addons")}
    if "quantity_mode" in cols:
        try:
            op.drop_column("department_service_addons", "quantity_mode")
        except Exception:
            pass
    if "service_scope" in cols:
        try:
            op.drop_column("department_service_addons", "service_scope")
        except Exception:
            pass
