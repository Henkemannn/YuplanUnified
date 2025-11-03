# Migrations

This project supports both Alembic (Python) migrations and optional raw SQL migrations for Postgres.

## Order of operations

1. Apply Alembic migrations as usual (these create/alter tables and add columns as needed).
2. For Postgres environments, apply the raw SQL guardrails to enforce `updated_at` consistency for optimistic concurrency:
   - `migrations/sql/2025-11-03_guardrails_updated_at.sql`

The SQL script is idempotent and safe to re-run. It performs:
- Backfill of NULL `updated_at` values
- Ensure `timestamptz` for `updated_at`
- Set `DEFAULT NOW() AT TIME ZONE 'UTC'`
- Install/replace `BEFORE UPDATE` triggers to bump `updated_at` on change

SQLite fallback is handled at the app layer and does not require triggers.

## Rollback hints (Postgres)

To rollback the guardrails manually if needed:

```sql
-- Users table
DROP TRIGGER IF EXISTS trg_set_updated_at_users ON users;
DROP FUNCTION IF EXISTS set_updated_at_users();
ALTER TABLE IF EXISTS users ALTER COLUMN updated_at DROP DEFAULT;

-- Tenant feature flags table
DROP TRIGGER IF EXISTS trg_set_updated_at_tff ON tenant_feature_flags;
DROP FUNCTION IF EXISTS set_updated_at_tff();
ALTER TABLE IF EXISTS tenant_feature_flags ALTER COLUMN updated_at DROP DEFAULT;
```

Note: Type changes to `timestamptz` are generally forward-only; plan rollbacks accordingly if you must revert the type.
