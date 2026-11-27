from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import (
    Column,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    engine_from_config,
    inspect,
    pool,
)

# Include core models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.config import Config
from core.db import ensure_sqlite_file_ready
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
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    try:
        ensure_sqlite_file_ready(config.get_main_option("sqlalchemy.url"))
    except Exception:
        # Keep existing Alembic behavior for non-sqlite or invalid URLs.
        pass
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            # SQLite defaults to non-transactional Alembic DDL. Begin the
            # physical write transaction before revision preflight or DDL.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                transactional_ddl=True,
            )
            try:
                context.run_migrations()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        else:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                transactional_ddl=True,
            )
            with context.begin_transaction():
                if connection.dialect.name == "postgresql":
                    Table(
                        "alembic_version",
                        MetaData(),
                        Column("version_num", String(128), nullable=False),
                        PrimaryKeyConstraint("version_num", name="alembic_version_pkc"),
                    ).create(connection, checkfirst=True)
                    columns = {
                        column["name"]: column
                        for column in inspect(connection).get_columns("alembic_version")
                    }
                    version_type = columns["version_num"]["type"]
                    if not isinstance(version_type, String):
                        raise RuntimeError("alembic_version.version_num must be a string")
                    if version_type.length is not None and version_type.length < 128:
                        connection.exec_driver_sql(
                            "ALTER TABLE alembic_version "
                            "ALTER COLUMN version_num TYPE VARCHAR(128)"
                        )
                context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
