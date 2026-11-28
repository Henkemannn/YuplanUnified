from sqlalchemy import text


def seed_historical_diet_reference_tables(conn):
    conn.execute(text(
        "CREATE TABLE diet_types (id VARCHAR(36) PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
        "premarked BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, version BIGINT NOT NULL DEFAULT 0)"
    ))
    conn.execute(text(
        "CREATE TABLE department_diet_defaults (department_id VARCHAR(36) NOT NULL "
        "REFERENCES departments(id), diet_type_id VARCHAR(36) NOT NULL REFERENCES diet_types(id), "
        "default_count INTEGER NOT NULL DEFAULT 0, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, version BIGINT NOT NULL DEFAULT 0, "
        "CONSTRAINT pk_department_diet_defaults PRIMARY KEY (department_id, diet_type_id))"
    ))
    conn.execute(text(
        "CREATE INDEX ix_department_diet_defaults_department ON department_diet_defaults(department_id)"
    ))
    conn.execute(text(
        "CREATE TABLE department_diet_overrides (department_id VARCHAR(64) NOT NULL, "
        "diet_type_id VARCHAR(64) NOT NULL, day INTEGER NOT NULL, meal VARCHAR(16) NOT NULL, "
        "count INTEGER NOT NULL DEFAULT 0, updated_at DATETIME, "
        "PRIMARY KEY (department_id, diet_type_id, day, meal))"
    ))
