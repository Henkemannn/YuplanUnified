"""Add residences table and nullable departments.residence_id

Revision ID: 0014_add_residences_and_department_residence
Revises: 0013_add_remember_to_order_items, 778407d29f47
Create Date: 2026-03-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0014_add_residences_and_department_residence"
down_revision = ("0013_add_remember_to_order_items", "778407d29f47")
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    try:
        cols = inspector.get_columns(table_name)
        return any(c.get("name") == column_name for c in cols)
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "residences" not in table_names:
        op.create_table(
            "residences",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("site_id", sa.String(64), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("site_id", "name", name="uq_residences_site_name"),
        )
        op.create_index("ix_residences_site_id", "residences", ["site_id"])

    if "departments" in table_names and not _has_column(inspector, "departments", "residence_id"):
        op.add_column("departments", sa.Column("residence_id", sa.String(64), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    if "departments" in table_names and _has_column(inspector, "departments", "residence_id"):
        op.drop_column("departments", "residence_id")

    if "residences" in table_names:
        try:
            op.drop_index("ix_residences_site_id", table_name="residences")
        except Exception:
            pass
        op.drop_table("residences")
