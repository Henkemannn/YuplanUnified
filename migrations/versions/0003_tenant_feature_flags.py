"""No-op migration after squashing tenant_feature_flags into 0001_init.

Revision ID: 0003_tenant_feature_flags
Revises: 0001_init
Create Date: 2025-09-29
"""
from __future__ import annotations

revision = "0003_tenant_feature_flags"
down_revision = "0001_init"
branch_labels = None
depends_on = None

def upgrade() -> None:  # pragma: no cover
    # Table already created in 0001_init (squashed). Intentionally empty.
    pass

def downgrade() -> None:  # pragma: no cover
    # Cannot reliably drop only this table because it's part of 0001 now.
    pass
