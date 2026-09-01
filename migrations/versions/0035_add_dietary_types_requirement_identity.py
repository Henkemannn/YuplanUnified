"""Add stable requirement identity to dietary_types

Revision ID: 0035_add_dietary_types_requirement_identity
Revises: 0034_add_dietary_types_site_id
Create Date: 2026-09-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision = "0035_add_dietary_types_requirement_identity"
down_revision = "0034_add_dietary_types_site_id"
branch_labels = None
depends_on = None


def _columns(inspector, table_name: str) -> set[str]:
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _indexes(inspector, table_name: str) -> list[dict]:
    try:
        return list(inspector.get_indexes(table_name))
    except Exception:
        return []


def _duplicate_requirement_keys(conn) -> bool:
    row = conn.execute(
        text(
            """
            SELECT requirement_key
            FROM dietary_types
            WHERE requirement_key IS NOT NULL AND trim(CAST(requirement_key AS TEXT)) <> ''
            GROUP BY requirement_key
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).fetchone()
    return row is not None


def _backfill(conn) -> None:
    conn.execute(
        text(
            """
            UPDATE dietary_types
            SET requirement_key = CASE
                WHEN requirement_key IS NULL OR trim(CAST(requirement_key AS TEXT)) = ''
                THEN 'legacy_' || CAST(id AS TEXT)
                ELSE requirement_key
            END,
            semantics = CASE
                WHEN semantics IS NULL OR trim(CAST(semantics AS TEXT)) = ''
                THEN 'legacy_bucket'
                WHEN lower(trim(CAST(semantics AS TEXT))) IN ('legacy_bucket', 'atomic')
                THEN lower(trim(CAST(semantics AS TEXT)))
                ELSE 'legacy_bucket'
            END
            """
        )
    )


def _validate_existing_semantics(conn) -> None:
    row = conn.execute(
        text(
            """
            SELECT id, semantics
            FROM dietary_types
            WHERE semantics IS NOT NULL AND trim(CAST(semantics AS TEXT)) <> ''
              AND lower(trim(CAST(semantics AS TEXT))) NOT IN ('legacy_bucket', 'atomic')
            LIMIT 1
            """
        )
    ).fetchone()
    if row is not None:
        raise RuntimeError(f"invalid preexisting semantics on dietary_types.id={row[0]}")


def _has_equivalent_requirement_key_unique(inspector) -> bool:
    for constraint in inspector.get_unique_constraints("dietary_types"):
        if list(constraint.get("column_names") or []) == ["requirement_key"]:
            return True
    for index in _indexes(inspector, "dietary_types"):
        if bool(index.get("unique")) and list(index.get("column_names") or []) == ["requirement_key"]:
            return True
    return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if "dietary_types" not in set(inspector.get_table_names()):
        return

    columns = _columns(inspector, "dietary_types")
    if "requirement_key" not in columns:
        op.add_column("dietary_types", sa.Column("requirement_key", sa.String(length=64), nullable=True))
    if "semantics" not in columns:
        op.add_column("dietary_types", sa.Column("semantics", sa.String(length=32), nullable=True))

    _validate_existing_semantics(conn)
    _backfill(conn)

    if _duplicate_requirement_keys(conn):
        raise RuntimeError("duplicate requirement_key values prevent unique constraint creation")

    if not _has_equivalent_requirement_key_unique(inspector):
        op.create_index(
            "uq_dietary_types_requirement_key",
            "dietary_types",
            ["requirement_key"],
            unique=True,
        )


def downgrade() -> None:
    """Conservative downgrade: keep identity columns/index in place."""
    return