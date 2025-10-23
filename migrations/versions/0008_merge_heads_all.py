"""Merge all active heads into a single linear history

Revision ID: 0008_merge_heads_all
Revises: 0002_audit_events, 0002_tenants, 0004_add_refresh_token_jti, 0007_add_task_timestamps
Create Date: 2025-10-22
"""
from __future__ import annotations

revision = "0008_merge_heads_all"
down_revision = (
    "0002_audit_events",
    "0002_tenants",
    "0004_add_refresh_token_jti",
    "0007_add_task_timestamps",
)
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover
    # No schema changes; this migration only merges branches.
    pass


def downgrade() -> None:  # pragma: no cover
    # Cannot unmerge cleanly.
    pass
