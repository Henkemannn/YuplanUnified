"""add audit_events table

Revision ID: 0002_audit_events
Revises: 0001_init
Create Date: 2025-10-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '0002_audit_events'
down_revision = '0001_init'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if 'audit_events' not in insp.get_table_names():
        op.create_table(
            'audit_events',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('ts', sa.DateTime, nullable=False),
            sa.Column('tenant_id', sa.Integer, nullable=True),
            sa.Column('actor_user_id', sa.Integer, nullable=True),
            sa.Column('actor_role', sa.String(length=50), nullable=True),
            sa.Column('event', sa.String(length=120), nullable=False),
            sa.Column('payload', sa.JSON, nullable=True),
            sa.Column('request_id', sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
            sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        )
    existing_idx = {ix['name'] for ix in insp.get_indexes('audit_events')} if 'audit_events' in insp.get_table_names() else set()
    if 'ix_audit_events_tenant_ts' not in existing_idx:
        try:
            op.create_index('ix_audit_events_tenant_ts', 'audit_events', ['tenant_id', 'ts'])
        except Exception:
            pass
    if 'ix_audit_events_event_ts' not in existing_idx:
        try:
            op.create_index('ix_audit_events_event_ts', 'audit_events', ['event', 'ts'])
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index('ix_audit_events_event_ts', table_name='audit_events')
    op.drop_index('ix_audit_events_tenant_ts', table_name='audit_events')
    op.drop_table('audit_events')
