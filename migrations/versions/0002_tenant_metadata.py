"""Tenant metadata table

Revision ID: 0002_tenant_metadata
Revises: 0001_init
Create Date: 2025-09-29
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '0002_tenant_metadata'
down_revision = '0001_init'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'tenant_metadata' not in inspector.get_table_names():
        op.create_table(
            'tenant_metadata',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, unique=True),
            sa.Column('kind', sa.String(length=40)),
            sa.Column('description', sa.String(length=255))
        )

def downgrade() -> None:
    op.drop_table('tenant_metadata')
