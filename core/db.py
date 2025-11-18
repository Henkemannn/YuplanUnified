"""Database engine + session management.
Later can be expanded with per-request session handling middleware.
"""

from __future__ import annotations

from contextlib import suppress

from sqlalchemy import create_engine, text
import os
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from .models import Base

_engine: Engine | None = None
_SessionFactory: scoped_session[Session] | None = None


def _normalize_url(url: str) -> str:
    # Normalize postgres schemes to ensure SQLAlchemy uses psycopg v3
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+" not in url.split("://",1)[1].split("@",1)[0]:
        # no explicit driver specified (defaults may try psycopg2), force psycopg
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def init_engine(database_url: str, force: bool = False) -> Engine:
    """Initialize global engine (idempotent) or reinitialize when force=True."""
    global _engine, _SessionFactory
    if _engine is None:
        database_url = _normalize_url(database_url)
        _engine = create_engine(database_url, future=True, echo=False)
        _SessionFactory = scoped_session(
            sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        )
        return _engine
    if force:
        _engine.dispose()
        database_url = _normalize_url(database_url)
        _engine = create_engine(database_url, future=True, echo=False)
        if _SessionFactory is not None:
            with suppress(Exception):  # pragma: no cover
                _SessionFactory.remove()
        _SessionFactory = scoped_session(
            sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        )
    return _engine


def get_session() -> Session:  # to be used inside request handlers (later integrate teardown)
    if _SessionFactory is None:
        raise RuntimeError("DB not initialized; call init_engine first")
    return _SessionFactory()


def get_new_session() -> Session:
    """Return a brand-new Session not bound to the thread-scoped registry.

    Useful for internal services that want isolation and predictable lifetime
    without affecting callers that might be using the scoped session.
    """
    if _engine is None:
        raise RuntimeError("DB not initialized; call init_engine first")
    factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return factory()


def create_all() -> (
    None
):  # dev helper ONLY for fresh ephemeral DBs (tests, scratch). Use Alembic in normal flows.
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    Base.metadata.create_all(_engine)
    # Test/dev fallback: create raw admin tables when using sqlite and migrations aren't applied.
    try:
        if _engine.dialect.name == "sqlite":  # lightweight fallback for tests
            # Guard to ensure this never runs in production by accident.
            if os.getenv("YP_ENABLE_SQLITE_BOOTSTRAP", "0") not in ("1", "true", "yes"):  # pragma: no cover - env driven
                return None
            with _engine.connect() as conn:
                # Sites table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS sites (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 0,
                        notes TEXT NULL,
                        updated_at TEXT
                    )
                """))
                # Departments table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS departments (
                        id TEXT PRIMARY KEY,
                        site_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        resident_count_mode TEXT NOT NULL,
                        resident_count_fixed INTEGER NOT NULL DEFAULT 0,
                        notes TEXT NULL,
                        version INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT
                    )
                """))
                # Diet defaults table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS department_diet_defaults (
                        department_id TEXT NOT NULL,
                        diet_type_id TEXT NOT NULL,
                        default_count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (department_id, diet_type_id)
                    )
                """))
                # Alt2 flags table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS alt2_flags (
                        site_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        week INTEGER NOT NULL,
                        weekday INTEGER NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT 0,
                        version INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT,
                        PRIMARY KEY (site_id, department_id, week, weekday)
                    )
                """))
    except Exception:
        # Silent fallback – tests will surface issues if schema still missing.
        pass
