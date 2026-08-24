"""Add owner-scoped offshore work menu decisions

Revision ID: 0030_add_offshore_work_menu_owner_scope
Revises: 20260723_offshore_work_menu
Create Date: 2026-08-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0030_add_offshore_work_menu_owner_scope"
down_revision = "20260723_offshore_work_menu"
branch_labels = None
depends_on = None


def _table_exists(inspector, name: str) -> bool:
    try:
        return name in inspector.get_table_names()
    except Exception:
        return False


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    try:
        return any(column["name"] == column_name for column in inspector.get_columns(table_name))
    except Exception:
        return False


def _unique_constraint_exists(inspector, table_name: str, constraint_name: str) -> bool:
    try:
        return any(constraint["name"] == constraint_name for constraint in inspector.get_unique_constraints(table_name))
    except Exception:
        return False


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    try:
        return any(index["name"] == index_name for index in inspector.get_indexes(table_name))
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, "offshore_work_menu_decisions"):
        return

    if not _column_exists(inspector, "offshore_work_menu_decisions", "owner_user_id"):
        with op.batch_alter_table("offshore_work_menu_decisions", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_offshore_work_menu_decisions_owner_user_id",
                "users",
                ["owner_user_id"],
                ["id"],
            )

    conn.execute(
        sa.text(
            """
            UPDATE offshore_work_menu_decisions
               SET owner_user_id = created_by_user_id
             WHERE owner_user_id IS NULL
               AND created_by_user_id IS NOT NULL
            """
        )
    )

    inspector = inspect(conn)
    with op.batch_alter_table("offshore_work_menu_decisions", recreate="always") as batch_op:
        if _unique_constraint_exists(inspector, "offshore_work_menu_decisions", "uq_offshore_work_menu_decisions_event_track"):
            batch_op.drop_constraint("uq_offshore_work_menu_decisions_event_track", type_="unique")
        if not _unique_constraint_exists(inspector, "offshore_work_menu_decisions", "uq_offshore_work_menu_decisions_event_track_owner"):
            batch_op.create_unique_constraint(
                "uq_offshore_work_menu_decisions_event_track_owner",
                ["tenant_id", "site_id", "service_event_id", "menu_track_key", "owner_user_id"],
            )

    inspector = inspect(conn)
    if not _index_exists(inspector, "offshore_work_menu_decisions", "ix_offshore_work_menu_decisions_tenant_site_event_owner"):
        op.create_index(
            "ix_offshore_work_menu_decisions_tenant_site_event_owner",
            "offshore_work_menu_decisions",
            ["tenant_id", "site_id", "service_event_id", "owner_user_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if not _table_exists(inspector, "offshore_work_menu_decisions"):
        return

    conflicting_rows = conn.execute(
        sa.text(
            """
            SELECT 1
              FROM offshore_work_menu_decisions
          GROUP BY tenant_id, site_id, service_event_id, menu_track_key
            HAVING COUNT(*) > 1
             LIMIT 1
            """
        )
    ).fetchone()
    if conflicting_rows is not None:
        raise RuntimeError(
            "Cannot safely downgrade offshore_work_menu_decisions while owner-scoped rows exist. "
            "Consolidate the data first, then retry the downgrade."
        )

    if _index_exists(inspector, "offshore_work_menu_decisions", "ix_offshore_work_menu_decisions_tenant_site_event_owner"):
        op.drop_index("ix_offshore_work_menu_decisions_tenant_site_event_owner", table_name="offshore_work_menu_decisions")

    with op.batch_alter_table("offshore_work_menu_decisions", recreate="always") as batch_op:
        if _unique_constraint_exists(inspector, "offshore_work_menu_decisions", "uq_offshore_work_menu_decisions_event_track_owner"):
            batch_op.drop_constraint("uq_offshore_work_menu_decisions_event_track_owner", type_="unique")
        if not _unique_constraint_exists(inspector, "offshore_work_menu_decisions", "uq_offshore_work_menu_decisions_event_track"):
            batch_op.create_unique_constraint(
                "uq_offshore_work_menu_decisions_event_track",
                ["tenant_id", "site_id", "service_event_id", "menu_track_key"],
            )
        batch_op.drop_column("owner_user_id")
