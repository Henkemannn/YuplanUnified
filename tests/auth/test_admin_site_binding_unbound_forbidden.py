import uuid
from core.app_factory import create_app
from core.db import get_session
from sqlalchemy import text
from werkzeug.security import generate_password_hash


def _temp_db_url():
    import os
    fname = f"test_{uuid.uuid4().hex}.db"
    base = os.path.abspath(os.path.join(os.getcwd()))
    return f"sqlite:///{os.path.join(base, fname)}"


def _ensure_schema(db):
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY,
            name TEXT,
            active INTEGER DEFAULT 1
        )
        """
    ))
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
            site_id TEXT NULL,
            refresh_token_jti TEXT,
            updated_at TEXT,
            deleted_at TEXT
        )
        """
    ))
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
    db.execute(text(
        """
        CREATE TABLE IF NOT EXISTS tenant_feature_flags (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER,
            name TEXT,
            enabled INTEGER DEFAULT 1,
            notes TEXT,
            updated_at TEXT
        )
        """
    ))
    db.commit()


def _seed_unbound_admin(db):
    _ensure_schema(db)
    tenant_id = 1
    db.execute(text("INSERT OR REPLACE INTO tenants(id,name,active) VALUES(1,'Primary',1)"))
    # Two sites in tenant
    site_a = f"s_{uuid.uuid4().hex[:6]}"
    site_b = f"s_{uuid.uuid4().hex[:6]}"
    db.execute(text("INSERT INTO sites(id,name,version,tenant_id) VALUES(:i,'Site A',0,:t)"), {"i": site_a, "t": tenant_id})
    db.execute(text("INSERT INTO sites(id,name,version,tenant_id) VALUES(:i,'Site B',0,:t)"), {"i": site_b, "t": tenant_id})
    # Create UNBOUND admin (site_id NULL)
    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Passw0rd!"
    db.execute(
        text("INSERT INTO users(tenant_id,email,password_hash,role,is_active,site_id) VALUES(:t,:e,:p,'admin',1,NULL)"),
        {"t": tenant_id, "e": email.lower(), "p": generate_password_hash(pw)},
    )
    db.commit()
    return {"tenant_id": tenant_id, "email": email, "password": pw, "site_a": site_a, "site_b": site_b}


def test_unbound_admin_cannot_view_selector_or_switch(monkeypatch):
    db_url = _temp_db_url()
    app = create_app({"TESTING": True, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    with app.app_context():
        db = get_session()
        seeded = _seed_unbound_admin(db)
        c = app.test_client()
        # Login to establish session
        r = c.post(
            "/ui/login",
            data={"email": seeded["email"], "password": seeded["password"]},
            follow_redirects=False,
        )
        assert r.status_code in (301, 302)
        # Attempt to view selector must be forbidden (403)
        r_sel = c.get("/ui/select-site", follow_redirects=False)
        assert r_sel.status_code == 403
        # Attempt to post a site choice must be forbidden (403)
        r_post = c.post("/ui/select-site", data={"site_id": seeded["site_b"], "next": "/ui/admin"}, follow_redirects=False)
        assert r_post.status_code == 403
