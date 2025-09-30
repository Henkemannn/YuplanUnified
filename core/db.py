"""Database engine + session management.
Later can be expanded with per-request session handling middleware.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import scoped_session, sessionmaker

from .models import Base

_engine: Engine | None = None
_SessionFactory: scoped_session | None = None


def init_engine(database_url: str, force: bool = False):
    """Initialize global engine (idempotent) or reinitialize when force=True."""
    global _engine, _SessionFactory
    if _engine is None:
        _engine = create_engine(database_url, future=True, echo=False)
        _SessionFactory = scoped_session(sessionmaker(bind=_engine, autoflush=False, autocommit=False))
        return _engine
    if force:
        _engine.dispose()
        _engine = create_engine(database_url, future=True, echo=False)
        if _SessionFactory is not None:
            try:
                _SessionFactory.remove()
            except Exception:  # pragma: no cover
                pass
        _SessionFactory = scoped_session(sessionmaker(bind=_engine, autoflush=False, autocommit=False))
    return _engine


def get_session():  # to be used inside request handlers (later integrate teardown)
    if _SessionFactory is None:
        raise RuntimeError("DB not initialized; call init_engine first")
    return _SessionFactory()


def create_all():  # dev helper ONLY for fresh ephemeral DBs (tests, scratch). Use Alembic in normal flows.
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    Base.metadata.create_all(_engine)
