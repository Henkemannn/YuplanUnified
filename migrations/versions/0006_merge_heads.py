"""Merge heads 0002_tenant_metadata and 0005_update_tasks_add_prep_fields

Revision ID: 0006_merge_heads
Revises: 0002_tenant_metadata, 0005_update_tasks_add_prep_fields
Create Date: 2025-09-29
"""
from __future__ import annotations

revision = "0006_merge_heads"
down_revision = ("0002_tenant_metadata", "0005_prep_fields")
branch_labels = None
depends_on = None

def upgrade() -> None:  # pragma: no cover
    # No structural changes; this migration only merges branches.
    pass

def downgrade() -> None:  # pragma: no cover
    # Cannot unmerge cleanly.
    pass
