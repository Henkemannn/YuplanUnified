"""add tenant columns: slug, theme, enabled, created_at"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0002_tenants'
down_revision = '0001_init'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    cols = {c['name'] for c in insp.get_columns('tenants')}
    if 'slug' not in cols:
        op.add_column('tenants', sa.Column('slug', sa.String(60), nullable=True))
    if 'theme' not in cols:
        op.add_column('tenants', sa.Column('theme', sa.Enum('ocean', 'emerald', name='tenanttheme'), nullable=True))
    if 'enabled' not in cols:
        op.add_column('tenants', sa.Column('enabled', sa.Boolean, nullable=False, server_default=sa.text('1')))
    if 'created_at' not in cols:
        op.add_column('tenants', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
    # unique on slug if not already present
    try:
        existing_ucs = {uc['name'] for uc in insp.get_unique_constraints('tenants')}
    except Exception:
        existing_ucs = set()
    if 'uq_tenants_slug' not in existing_ucs:
        try:
            op.create_unique_constraint('uq_tenants_slug', 'tenants', ['slug'])
        except Exception:
            pass

def downgrade():
    try:
        op.drop_constraint('uq_tenants_slug', 'tenants', type_='unique')
    except Exception:
        pass
    try:
        op.drop_column('tenants', 'created_at')
        op.drop_column('tenants', 'enabled')
        op.drop_column('tenants', 'theme')
        op.drop_column('tenants', 'slug')
    except Exception:
        pass