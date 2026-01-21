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
    # For sqlite test runs we want a clean schema each invocation to avoid
    # primary key collisions when tests call create_all() multiple times.
    if _engine.dialect.name == "sqlite":
        try:
            Base.metadata.drop_all(_engine)
        except Exception:
            pass
    Base.metadata.create_all(_engine)
    # Align SQLite test schema with production migrations for specific tables
    try:
        if _engine.dialect.name == "sqlite":
            with _engine.connect() as conn:
                # Helper: get existing columns for a table
                def _cols(table: str) -> set[str]:
                    rows = conn.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
                    return {str(r[1]) for r in rows}

                # MENUS: add status + updated_at if missing
                try:
                    if "menus" in {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}:
                        mcols = _cols("menus")
                        if "status" not in mcols:
                            conn.execute(text("ALTER TABLE menus ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'"))
                        if "updated_at" not in mcols:
                            conn.execute(text("ALTER TABLE menus ADD COLUMN updated_at TEXT NULL"))
                        # Ensure existing rows have a non-null updated_at to support ETag generation
                        conn.execute(text("UPDATE menus SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL"))
                except Exception:
                    pass

                # USERS: add username, full_name, is_active if missing; ensure unique(username)
                try:
                    if "users" in {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}:
                        ucols = _cols("users")
                        if "username" not in ucols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN username TEXT"))
                        if "full_name" not in ucols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN full_name TEXT NULL"))
                        if "is_active" not in ucols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"))
                        # Create a unique index for username if it doesn't exist
                        try:
                            idx_rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name='ux_users_username'"))
                            has_idx = idx_rows.fetchone() is not None
                        except Exception:
                            has_idx = False
                        if not has_idx:
                            # Only create the index if column exists now
                            if "username" in _cols("users"):
                                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username ON users(username)"))
                        # Backfill is_active to 1 where NULL (defensive if prior partial rows exist)
                        conn.execute(text("UPDATE users SET is_active = COALESCE(is_active, 1) WHERE is_active IS NULL"))
                except Exception:
                    pass

                # WEEKVIEW ALT2 FLAGS: canonicalize to site-scoped schema
                try:
                    # Detect existing table
                    names = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
                    if "weekview_alt2_flags" in names:
                        wcols = _cols("weekview_alt2_flags")
                        is_canonical = ("site_id" in wcols) and ("enabled" in wcols) and ("tenant_id" not in wcols) and ("is_alt2" not in wcols)
                        if not is_canonical:
                            # Create canonical table with proper UNIQUE constraint
                            conn.execute(text(
                                """
                                CREATE TABLE IF NOT EXISTS weekview_alt2_flags_new (
                                    site_id TEXT NOT NULL,
                                    department_id TEXT NOT NULL,
                                    year INTEGER NOT NULL,
                                    week INTEGER NOT NULL,
                                    day_of_week INTEGER NOT NULL,
                                    enabled INTEGER NOT NULL DEFAULT 0,
                                    UNIQUE (site_id, department_id, year, week, day_of_week)
                                );
                                """
                            ))
                            # Try to migrate legacy data if present
                            # Legacy columns: tenant_id, department_id, year, week, day_of_week, is_alt2
                            try:
                                if "department_id" in wcols and "year" in wcols and "week" in wcols and "day_of_week" in wcols:
                                    # Use departments.site_id to backfill site_id
                                    conn.execute(text(
                                        """
                                        INSERT INTO weekview_alt2_flags_new(site_id, department_id, year, week, day_of_week, enabled)
                                        SELECT d.site_id, w.department_id, w.year, w.week, w.day_of_week,
                                               CASE WHEN COALESCE(w.is_alt2, 0) = 1 THEN 1 ELSE 0 END
                                        FROM weekview_alt2_flags w
                                        LEFT JOIN departments d ON d.id = w.department_id
                                        WHERE COALESCE(w.is_alt2, 0) = 1 AND d.site_id IS NOT NULL
                                        """
                                    ))
                            except Exception:
                                # If migration fails, continue with empty canonical table
                                pass
                            # Replace legacy table with canonical
                            conn.execute(text("DROP TABLE IF EXISTS weekview_alt2_flags"))
                            conn.execute(text("ALTER TABLE weekview_alt2_flags_new RENAME TO weekview_alt2_flags"))
                    else:
                        # No table yet; create canonical one
                        conn.execute(text(
                            """
                            CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
                                site_id TEXT NOT NULL,
                                department_id TEXT NOT NULL,
                                year INTEGER NOT NULL,
                                week INTEGER NOT NULL,
                                day_of_week INTEGER NOT NULL,
                                enabled INTEGER NOT NULL DEFAULT 0,
                                UNIQUE (site_id, department_id, year, week, day_of_week)
                            );
                            """
                        ))
                except Exception:
                    pass

                conn.commit()
    except Exception:
        # Silent: tests that rely on these columns will reveal issues if misaligned
        pass
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
                # Weekview Alt2 flags table (legacy/weekview compatibility)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS weekview_alt2_flags (
                        site_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        day_of_week INTEGER NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 0,
                        UNIQUE (site_id, department_id, year, week, day_of_week)
                    )
                """))
                # Weekview items table (for menus)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS weekview_items (
                        id TEXT PRIMARY KEY,
                        tenant_id INTEGER NOT NULL,
                        department_id TEXT NOT NULL,
                        local_date TEXT NOT NULL,
                        meal TEXT NOT NULL,
                        title TEXT NOT NULL,
                        notes TEXT,
                        status TEXT,
                        version INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT
                    )
                """))
                conn.commit()
    except Exception:
        # Silent fallback – tests will surface issues if schema still missing.
        pass


def get_site_tenant(site_id: str) -> int | None:
    """Return the tenant_id for a given site_id, or None if unavailable.

    SQLite dev schemas may lack sites.tenant_id; in that case we safely return None.
    """
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    # Prefer session helper to reuse connection pool
    try:
        sess = get_session()
    except Exception:
        sess = None
    try:
        conn = (sess.connection() if sess is not None else _engine.connect())
        try:
            # Detect SQLite column presence via PRAGMA
            if conn.dialect.name == "sqlite":
                try:
                    rows = conn.execute(text("PRAGMA table_info('sites')")).fetchall()
                    cols = {str(r[1]) for r in rows}
                    if "tenant_id" not in cols:
                        return None
                except Exception:
                    return None
            row = conn.execute(text("SELECT tenant_id FROM sites WHERE id = :sid"), {"sid": site_id}).fetchone()
            if not row:
                return None
            val = row[0]
            return int(val) if val is not None else None
        finally:
            try:
                if sess is None:
                    conn.close()
            except Exception:
                pass
    finally:
        try:
            if sess is not None:
                sess.close()
        except Exception:
            pass
