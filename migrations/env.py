from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Include core models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.config import Config
from core.models import Base

# this is the Alembic Config object
config = context.config

# Override URL from env (if provided)
db_url = os.getenv("DATABASE_URL")
if db_url:
    # Normalize common variants to SQLAlchemy 2 + psycopg v3 driver
    # - fly attach often yields postgres:// -> use postgresql+psycopg://
    # - plain postgresql:// (no +driver) may choose psycopg2 by default; force psycopg v3
    norm = db_url
    if norm.startswith("postgres://"):
        norm = "postgresql+psycopg://" + norm[len("postgres://") :]
    elif norm.startswith("postgresql://") and "+" not in norm.split("://", 1)[1].split("@", 1)[0]:
        # no explicit driver specified before host, e.g. postgresql://user:pass@host/db
        norm = "postgresql+psycopg://" + norm[len("postgresql://") :]
    config.set_main_option("sqlalchemy.url", norm)

# Interpret the config file for Python logging.
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Preflight: widen alembic_version.version_num for Postgres if too short
        try:
            dialect = connection.dialect.name
            if dialect == "postgresql":
                # Use an explicit transaction for DDL safety
                trans = connection.begin()
                try:
                    res = connection.exec_driver_sql(
                        """
                        SELECT character_maximum_length
                        FROM information_schema.columns
                        WHERE table_name = 'alembic_version'
                          AND column_name = 'version_num'
                          AND table_schema = current_schema()
                        """
                    ).fetchone()
                    current_len = res[0] if res else None
                    if current_len is not None and current_len < 64:
                        connection.exec_driver_sql(
                            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
                        )
                    elif current_len is None:
                        # Table might not exist yet; best-effort unconditional widen guarded by try/except
                        try:
                            connection.exec_driver_sql(
                                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
                            )
                        except Exception:
                            pass
                    # else: already wide enough
                    trans.commit()
                except Exception:
                    trans.rollback()
        except Exception:
            # Never block migrations due to preflight check
            pass

        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
