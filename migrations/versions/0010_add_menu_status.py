"""Add status field to menus table for draft/published workflow

Revision ID: 0010_add_menu_status
Revises: 0009_merge_audit_into_main
Create Date: 2025-11-26

This migration adds a status column to the menus table to support
draft/published workflow for menu management.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010_add_menu_status"
down_revision = "0009_merge_audit_into_main"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add status column to menus table with default 'draft'."""
    # Add status column with default value
    op.add_column(
        'menus',
        sa.Column('status', sa.String(20), nullable=False, server_default='draft')
    )
    
    # Create index for better query performance
    op.create_index('ix_menus_status', 'menus', ['status'])


def downgrade() -> None:
    """Remove status column from menus table."""
    op.drop_index('ix_menus_status', table_name='menus')
    op.drop_column('menus', 'status')
