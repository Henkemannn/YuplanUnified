"""DB guardrails for updated_at: defaults, triggers, backfill

Revision ID: 0002_updated_at_guardrails
Revises: 0001_init
Create Date: 2025-11-03
"""
from __future__ import annotations

from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "0002_updated_at_guardrails"
down_revision = "0001_init"
branch_labels = None
depends_on = None


POSTGRES_TRIGGER_FN = r"""
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

POSTGRES_CREATE_TRIGGERS = [
    "CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();",
    "CREATE TRIGGER tenant_feature_flags_set_updated_at BEFORE UPDATE ON tenant_feature_flags FOR EACH ROW EXECUTE FUNCTION set_updated_at();",
]

POSTGRES_DROP_TRIGGERS = [
    "DROP TRIGGER IF EXISTS users_set_updated_at ON users;",
    "DROP TRIGGER IF EXISTS tenant_feature_flags_set_updated_at ON tenant_feature_flags;",
    "DROP FUNCTION IF EXISTS set_updated_at();",
]

def _is_postgres(conn: Connection) -> bool:
    return (getattr(getattr(conn, "dialect", None), "name", "") == "postgresql")


def upgrade():  # pragma: no cover (migration exercised indirectly in tests)
    conn = op.get_bind()
    # Backfill: set updated_at where NULL
    op.execute("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;")
    op.execute("UPDATE tenant_feature_flags SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;")

    if _is_postgres(conn):
        # Defaults to current time for new/updated records
        op.execute("ALTER TABLE users ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;")
        op.execute("ALTER TABLE tenant_feature_flags ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;")
        # Triggers to bump updated_at on UPDATE
        op.execute(POSTGRES_TRIGGER_FN)
        for stmt in POSTGRES_CREATE_TRIGGERS:
            op.execute(stmt)
    else:
        # SQLite fallback: rely on app-layer to bump updated_at; defaults/backfill above suffice
        pass


def downgrade():  # pragma: no cover
    conn = op.get_bind()
    if _is_postgres(conn):
        for stmt in POSTGRES_DROP_TRIGGERS:
            op.execute(stmt)
        # Clear defaults
        op.execute("ALTER TABLE users ALTER COLUMN updated_at DROP DEFAULT;")
        op.execute("ALTER TABLE tenant_feature_flags ALTER COLUMN updated_at DROP DEFAULT;")
