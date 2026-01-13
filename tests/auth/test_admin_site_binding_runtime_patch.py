import uuid
import os
from core.app_factory import create_app
from core.db import get_session
from sqlalchemy import text
from werkzeug.security import generate_password_hash


def _temp_db_url():
    fname = f"test_{uuid.uuid4().hex}.db"
    base = os.path.abspath(os.path.join(os.getcwd()))
    return f"sqlite:///{os.path.join(base, fname)}"


def test_app_startup_adds_users_site_id_and_login_succeeds():
    db_url = _temp_db_url()
    app = create_app({"TESTING": True, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    # Create minimal schema without users.site_id
    with app.app_context():
        db = get_session()
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY,
                name TEXT,
                active INTEGER DEFAULT 1
            )
        """))
        db.execute(text("""
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
                refresh_token_jti TEXT,
                updated_at TEXT,
                deleted_at TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS sites (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version INTEGER DEFAULT 0,
                tenant_id INTEGER
            )
        """))
        # Seed two sites for selector behavior
        tenant_id = 1
        db.execute(text("INSERT OR REPLACE INTO tenants(id,name,active) VALUES(1,'Primary',1)"))
        s1 = f"s_{uuid.uuid4().hex[:6]}"
        s2 = f"s_{uuid.uuid4().hex[:6]}"
        db.execute(text("INSERT INTO sites(id,name,version,tenant_id) VALUES(:i,'A',0,:t)"), {"i": s1, "t": tenant_id})
        db.execute(text("INSERT INTO sites(id,name,version,tenant_id) VALUES(:i,'B',0,:t)"), {"i": s2, "t": tenant_id})
        # Create admin user (no site binding)
        email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
        pw = "Passw0rd!"
        db.execute(text("INSERT INTO users(tenant_id,email,password_hash,role,is_active) VALUES(:t,:e,:p,'admin',1)"), {"t": tenant_id, "e": email.lower(), "p": generate_password_hash(pw)})
        db.commit()
        # Verify column doesn't exist yet
        cols = db.execute(text("PRAGMA table_info('users')")).fetchall()
        assert not any(str(c[1]) == "site_id" for c in cols)
    # Make a fresh app to trigger runtime alignment (non-TESTING path may skip, but alignment in create_app is guarded)
    app2 = create_app({"TESTING": False, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    with app2.app_context():
        db2 = get_session()
        cols2 = db2.execute(text("PRAGMA table_info('users')")).fetchall()
        assert any(str(c[1]) == "site_id" for c in cols2)
        c = app2.test_client()
        r = c.post("/auth/login", data={"email": email, "password": pw}, headers={"Accept": "text/html"}, follow_redirects=False)
        # Should not 500; likely redirects to selector (since two sites)
        assert r.status_code in (301, 302)
        loc = r.headers.get("Location") or ""
        assert "/ui/select-site" in loc
