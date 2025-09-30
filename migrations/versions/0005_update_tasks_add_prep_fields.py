"""Add prep task fields to tasks

Revision ID: 0005_update_tasks_add_prep_fields
Revises: 0004_add_notes
Create Date: 2025-09-29
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0005_update_tasks_add_prep_fields'
down_revision = '0004_add_notes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    cols = {c['name'] for c in inspector.get_columns('tasks')}
    needed = []
    if 'menu_id' not in cols:
        needed.append(sa.Column('menu_id', sa.Integer(), sa.ForeignKey('menus.id')))
    if 'dish_id' not in cols:
        needed.append(sa.Column('dish_id', sa.Integer(), sa.ForeignKey('dishes.id')))
    if 'private_flag' not in cols:
        needed.append(sa.Column('private_flag', sa.Boolean(), server_default=sa.text('0'), nullable=False))
    if 'assignee_id' not in cols:
        needed.append(sa.Column('assignee_id', sa.Integer(), sa.ForeignKey('users.id')))
    if 'creator_user_id' not in cols:
        needed.append(sa.Column('creator_user_id', sa.Integer(), sa.ForeignKey('users.id')))
    if needed:
        with op.batch_alter_table('tasks') as batch:
            for col in needed:
                batch.add_column(col)
    # Index
    existing_idx = {ix['name'] for ix in inspector.get_indexes('tasks')}
    if 'ix_tasks_tenant_done_private' not in existing_idx:
        try:
            op.create_index('ix_tasks_tenant_done_private', 'tasks', ['tenant_id','done','private_flag'])
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index('ix_tasks_tenant_done_private', table_name='tasks')
    with op.batch_alter_table('tasks') as batch:
        batch.drop_column('creator_user_id')
        batch.drop_column('assignee_id')
        batch.drop_column('private_flag')
        batch.drop_column('dish_id')
        batch.drop_column('menu_id')
