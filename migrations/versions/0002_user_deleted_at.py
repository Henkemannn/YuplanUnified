"""add deleted_at to users

Revision ID: 0002_user_deleted_at
Revises: 0001_init
Create Date: 2025-11-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_user_deleted_at'
down_revision = '0001_init'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'deleted_at')
