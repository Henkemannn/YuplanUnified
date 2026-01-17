import sys
import sqlite3
import pytest
from sqlalchemy import text

@pytest.fixture(autouse=True)
def _ensure_auth_schema(monkeypatch):
    """Ensure minimal schema exists for auth tests that call create_app directly.

    Tests in auth may construct the app without using the session-wide app fixture,
    and then seed via ORM before any bootstrap runs. We patch create_app to align
    a minimal SQLite schema (tenants, users, sites) in TESTING to avoid 'no such table'.
    """
    try:
        from core.app_factory import create_app as _real_create_app
        from core.db import get_session
    except Exception:
        return

    def _patched_create_app(cfg_override=None):
        app = _real_create_app(cfg_override)
        try:
            # Only adjust SQLite ephemeral test DBs
            with app.app_context():
                db = get_session()
                try:
                    dialect = (db.bind.dialect.name if getattr(db, 'bind', None) else 'sqlite')
                    if dialect == 'sqlite':
                        # Tenants table (minimal)
                        db.execute(text(
                            """
                            CREATE TABLE IF NOT EXISTS tenants (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT UNIQUE NOT NULL,
                                active INTEGER DEFAULT 1
                            )
                            """
                        ))
                        # Users table (aligned with auth needs)
                        db.execute(text(
                            """
                            CREATE TABLE IF NOT EXISTS users (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                tenant_id INTEGER,
                                username TEXT,
                                email TEXT UNIQUE,
                                password_hash TEXT,
                                role TEXT,
                                full_name TEXT,
                                is_active INTEGER DEFAULT 1,
                                unit_id INTEGER,
                                site_id TEXT,
                                refresh_token_jti TEXT,
                                updated_at TEXT,
                                deleted_at TEXT
                            )
                            """
                        ))
                        # Sites table (used by admin flows)
                        db.execute(text(
                            """
                            CREATE TABLE IF NOT EXISTS sites (
                                id TEXT PRIMARY KEY,
                                name TEXT NOT NULL,
                                version INTEGER DEFAULT 0,
                                tenant_id INTEGER
                            )
                            """
                        ))
                        db.commit()
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
        except Exception:
            # Best effort; do not fail app creation in tests
            pass
        return app

    # Patch only within auth tests scope
    monkeypatch.setattr('core.app_factory.create_app', _patched_create_app, raising=True)
    # Also patch any auth test modules that imported the symbol directly
    for mod_name, mod in list(sys.modules.items()):
        try:
            if not mod_name.startswith('tests.auth.'):
                continue
            if hasattr(mod, 'create_app'):
                monkeypatch.setattr(mod, 'create_app', _patched_create_app, raising=True)
        except Exception:
            continue

    # Proactively ensure default dev.db has minimal schema for tests that use defaults
    try:
        conn = sqlite3.connect('dev.db')
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                active INTEGER DEFAULT 1
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                username TEXT,
                email TEXT UNIQUE,
                password_hash TEXT,
                role TEXT,
                full_name TEXT,
                is_active INTEGER DEFAULT 1,
                unit_id INTEGER,
                site_id TEXT,
                refresh_token_jti TEXT,
                updated_at TEXT,
                deleted_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sites (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version INTEGER DEFAULT 0,
                tenant_id INTEGER
            )
            """
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
