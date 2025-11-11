"""Merge outstanding head 0002_audit_events into main line (0008_admin_phase_b)

Revision ID: 0009_merge_audit_into_main
Revises: 0008_admin_phase_b, 0002_audit_events, 0004_add_refresh_token_jti
Create Date: 2025-11-11
"""
from __future__ import annotations

revision = "0009_merge_audit_into_main"
down_revision = ("0008_admin_phase_b", "0002_audit_events", "0004_add_refresh_token_jti")
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover
    # Merge migration only; no schema changes required.
    pass


def downgrade() -> None:  # pragma: no cover
    # Cannot unmerge cleanly.
    pass
