CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS weekview_registrations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  department_id uuid NOT NULL,
  year integer NOT NULL,
  week integer NOT NULL CHECK (week BETWEEN 1 AND 53),
  day_of_week integer NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
  meal text NOT NULL CHECK (meal IN ('lunch','dinner')),
  diet_type text NOT NULL,
  marked boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, department_id, year, week, day_of_week, meal, diet_type)
);

CREATE TABLE IF NOT EXISTS weekview_residents_count (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  department_id uuid NOT NULL,
  year integer NOT NULL,
  week integer NOT NULL,
  day_of_week integer NOT NULL,
  meal text NOT NULL,
  count integer NOT NULL CHECK (count >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, department_id, year, week, day_of_week, meal)
);

CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  department_id uuid NOT NULL,
  year integer NOT NULL,
  week integer NOT NULL,
  day_of_week integer NOT NULL,
  is_alt2 boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, department_id, year, week, day_of_week)
);

CREATE TABLE IF NOT EXISTS weekview_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  department_id uuid NOT NULL,
  year integer NOT NULL,
  week integer NOT NULL,
  version integer NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, department_id, year, week)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS ix_wv_reg_tenant_dept_year_week ON weekview_registrations(tenant_id, department_id, year, week);
CREATE INDEX IF NOT EXISTS ix_wv_reg_tenant_year_week ON weekview_registrations(tenant_id, year, week);
CREATE INDEX IF NOT EXISTS ix_wv_res_tenant_dept_year_week ON weekview_residents_count(tenant_id, department_id, year, week);
CREATE INDEX IF NOT EXISTS ix_wv_res_tenant_year_week ON weekview_residents_count(tenant_id, year, week);
CREATE INDEX IF NOT EXISTS ix_wv_alt2_tenant_dept_year_week ON weekview_alt2_flags(tenant_id, department_id, year, week);
CREATE INDEX IF NOT EXISTS ix_wv_alt2_tenant_year_week ON weekview_alt2_flags(tenant_id, year, week);

-- Trigger function to bump version
CREATE OR REPLACE FUNCTION bump_weekview_version()
RETURNS TRIGGER AS $$
DECLARE
  v_tenant uuid;
  v_dept uuid;
  v_year integer;
  v_week integer;
BEGIN
  v_tenant := COALESCE(NEW.tenant_id, OLD.tenant_id);
  v_dept := COALESCE(NEW.department_id, OLD.department_id);
  v_year := COALESCE(NEW.year, OLD.year);
  v_week := COALESCE(NEW.week, OLD.week);

  UPDATE weekview_versions
  SET version = version + 1, updated_at = now()
  WHERE tenant_id = v_tenant AND department_id = v_dept AND year = v_year AND week = v_week;
  IF NOT FOUND THEN
    INSERT INTO weekview_versions(tenant_id, department_id, year, week, version)
    VALUES(v_tenant, v_dept, v_year, v_week, 1)
    ON CONFLICT (tenant_id, department_id, year, week) DO UPDATE SET version = weekview_versions.version + 1, updated_at = now();
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- updated_at triggers
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach triggers
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wv_reg_updated_at'
  ) THEN
    CREATE TRIGGER trg_wv_reg_updated_at BEFORE UPDATE ON weekview_registrations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wv_reg_bump_version'
  ) THEN
    CREATE TRIGGER trg_wv_reg_bump_version AFTER INSERT OR UPDATE OR DELETE ON weekview_registrations
    FOR EACH ROW EXECUTE FUNCTION bump_weekview_version();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wv_res_updated_at'
  ) THEN
    CREATE TRIGGER trg_wv_res_updated_at BEFORE UPDATE ON weekview_residents_count
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wv_res_bump_version'
  ) THEN
    CREATE TRIGGER trg_wv_res_bump_version AFTER INSERT OR UPDATE OR DELETE ON weekview_residents_count
    FOR EACH ROW EXECUTE FUNCTION bump_weekview_version();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wv_alt2_updated_at'
  ) THEN
    CREATE TRIGGER trg_wv_alt2_updated_at BEFORE UPDATE ON weekview_alt2_flags
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wv_alt2_bump_version'
  ) THEN
    CREATE TRIGGER trg_wv_alt2_bump_version AFTER INSERT OR UPDATE OR DELETE ON weekview_alt2_flags
    FOR EACH ROW EXECUTE FUNCTION bump_weekview_version();
  END IF;
END;
$$;