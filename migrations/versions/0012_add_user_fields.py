"""Add username, full_name, is_active to users

Revision ID: 0012_add_user_fields
Revises: 0011_add_menu_updated_at
Create Date: 2025-11-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_add_user_fields"
down_revision = "0011_add_menu_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else "sqlite"
    true_def = sa.text("TRUE") if dialect == "postgresql" else sa.text("1")
    
    # Add username column (nullable initially for existing users)
    op.add_column("users", sa.Column("username", sa.String(length=100), nullable=True))
    
    # Add full_name column (nullable)
    op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))
    
    # Add is_active column (default True)
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=true_def))
    
    # For existing users without username, set username = email prefix
    # This ensures backward compatibility
    conn.execute(sa.text("UPDATE users SET username = email WHERE username IS NULL"))
    
    # Now make username NOT NULL and UNIQUE
    # SQLite requires recreating table for constraints
    if dialect == "sqlite":
        # Create unique index instead
        op.create_index("ix_users_username_unique", "users", ["username"], unique=True)
    else:
        # PostgreSQL can alter column
        op.alter_column("users", "username", nullable=False)
        op.create_unique_constraint("uq_users_username", "users", ["username"])


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name if conn is not None else "sqlite"
    
    if dialect == "sqlite":
        op.drop_index("ix_users_username_unique", table_name="users")
    else:
        op.drop_constraint("uq_users_username", "users", type_="unique")
    
    op.drop_column("users", "is_active")
    op.drop_column("users", "full_name")
    op.drop_column("users", "username")
