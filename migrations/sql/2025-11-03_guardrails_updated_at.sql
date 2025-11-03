-- Guardrails for updated_at: backfill, default, and update triggers (PostgreSQL)
-- Safe to run multiple times; uses CREATE OR REPLACE and conditional drops.

-- Note: TYPE change is idempotent if already timestamptz
ALTER TABLE IF EXISTS users
  ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';

-- 2) Backfill NULLs with current UTC timestamp
UPDATE users SET updated_at = NOW() AT TIME ZONE 'UTC' WHERE updated_at IS NULL;

ALTER TABLE IF EXISTS users
  ALTER COLUMN updated_at SET DEFAULT (NOW() AT TIME ZONE 'UTC');

-- 4) Upsert trigger function to bump updated_at on any UPDATE
CREATE OR REPLACE FUNCTION set_updated_at_users() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := NOW() AT TIME ZONE 'UTC';
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5) Replace existing trigger
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_set_updated_at_users' AND NOT tgisinternal
  ) THEN
    DROP TRIGGER trg_set_updated_at_users ON users;
  END IF;
  CREATE TRIGGER trg_set_updated_at_users
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at_users();
END;
$$;


ALTER TABLE IF EXISTS tenant_feature_flags
  ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';

-- 2) Backfill NULLs with current UTC timestamp
UPDATE tenant_feature_flags SET updated_at = NOW() AT TIME ZONE 'UTC' WHERE updated_at IS NULL;

ALTER TABLE IF EXISTS tenant_feature_flags
  ALTER COLUMN updated_at SET DEFAULT (NOW() AT TIME ZONE 'UTC');

-- 4) Upsert trigger function to bump updated_at on any UPDATE
CREATE OR REPLACE FUNCTION set_updated_at_tff() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := NOW() AT TIME ZONE 'UTC';
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5) Replace existing trigger
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_set_updated_at_tff' AND NOT tgisinternal
  ) THEN
    DROP TRIGGER trg_set_updated_at_tff ON tenant_feature_flags;
  END IF;
  CREATE TRIGGER trg_set_updated_at_tff
    BEFORE UPDATE ON tenant_feature_flags
    FOR EACH ROW EXECUTE FUNCTION set_updated_at_tff();
END;
$$;

-- ROLLBACK NOTES ------------------------------------------------------------
-- To rollback defaults and triggers (manual):
--   DROP TRIGGER IF EXISTS trg_set_updated_at_users ON users;
--   DROP FUNCTION IF EXISTS set_updated_at_users();
--   ALTER TABLE IF EXISTS users ALTER COLUMN updated_at DROP DEFAULT;
--
--   DROP TRIGGER IF EXISTS trg_set_updated_at_tff ON tenant_feature_flags;
--   DROP FUNCTION IF EXISTS set_updated_at_tff();
--   ALTER TABLE IF EXISTS tenant_feature_flags ALTER COLUMN updated_at DROP DEFAULT;
