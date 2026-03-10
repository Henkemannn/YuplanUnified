"""Merge remaining heads so `alembic upgrade head` works on fresh databases.

Revision ID: 0015_merge_all_heads
Revises: 0014_add_residences_and_department_residence, 0002_add_site_id_to_menus, 0002_user_deleted_at
Create Date: 2026-03-10
"""

from __future__ import annotations


# revision identifiers, used by Alembic.
revision = "0015_merge_all_heads"
down_revision = (
    "0014_add_residences_and_department_residence",
    "0002_add_site_id_to_menus",
    "0002_user_deleted_at",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge-only revision: no schema changes.
    pass


def downgrade() -> None:
    pass
