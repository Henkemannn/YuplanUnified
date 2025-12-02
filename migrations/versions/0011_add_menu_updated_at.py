"""Add updated_at column to menus table for ETag support

Revision ID: 0011_add_menu_updated_at
Revises: 0010_add_menu_status
Create Date: 2025-11-26

This migration adds an updated_at timestamp column to the menus table
to support ETag-based optimistic locking for concurrent editing.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0011_add_menu_updated_at"
down_revision = "0010_add_menu_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add updated_at column to menus table."""
    # Add updated_at column with default to current timestamp
    op.add_column(
        'menus',
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP')
        )
    )
    
    # For PostgreSQL, create trigger to auto-update timestamp
    # For SQLite, this will be handled in application code
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("""
            CREATE OR REPLACE FUNCTION update_menus_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        op.execute("""
            CREATE TRIGGER menus_updated_at_trigger
            BEFORE UPDATE ON menus
            FOR EACH ROW
            EXECUTE FUNCTION update_menus_updated_at();
        """)


def downgrade() -> None:
    """Remove updated_at column from menus table."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP TRIGGER IF EXISTS menus_updated_at_trigger ON menus")
        op.execute("DROP FUNCTION IF EXISTS update_menus_updated_at()")
    
    op.drop_column('menus', 'updated_at')
