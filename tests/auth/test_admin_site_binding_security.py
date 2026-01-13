import uuid
from flask import session as _session
from core.app_factory import create_app
from core.db import get_session
from sqlalchemy import text
from werkzeug.security import generate_password_hash


def _temp_db_url():
    import os
    fname = f"test_{uuid.uuid4().hex}.db"
    base = os.path.abspath(os.path.join(os.getcwd()))
    return f"sqlite:///{os.path.join(base, fname)}"


def _ensure_schema_with_binding(db):
    # Minimal schema with users.site_id present
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
    # Minimal feature flags table to satisfy before_request loader
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


def _seed_bound_admin(db):
    _ensure_schema_with_binding(db)
    tenant_id = 1
    db.execute(text("INSERT OR REPLACE INTO tenants(id,name,active) VALUES(1,'Primary',1)"))
    # Two sites
    site_a = f"s_{uuid.uuid4().hex[:6]}"
    site_b = f"s_{uuid.uuid4().hex[:6]}"
    db.execute(text("INSERT INTO sites(id,name,version,tenant_id) VALUES(:i,'Site A',0,:t)"), {"i": site_a, "t": tenant_id})
    db.execute(text("INSERT INTO sites(id,name,version,tenant_id) VALUES(:i,'Site B',0,:t)"), {"i": site_b, "t": tenant_id})
    # Create bound admin user (site_id = site_a)
    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Passw0rd!"
    db.execute(
        text("INSERT INTO users(tenant_id,email,password_hash,role,is_active,site_id) VALUES(:t,:e,:p,'admin',1,:s)"),
        {"t": tenant_id, "e": email.lower(), "p": generate_password_hash(pw), "s": site_a},
    )
    db.commit()
    return {"tenant_id": tenant_id, "email": email, "password": pw, "site_a": site_a, "site_b": site_b}


def test_bound_admin_login_skips_selector_and_forces_site(monkeypatch):
    db_url = _temp_db_url()
    app = create_app({"TESTING": True, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    with app.app_context():
        db = get_session()
        seeded = _seed_bound_admin(db)
        c = app.test_client()
        r = c.post(
            "/auth/login",
            data={"email": seeded["email"], "password": seeded["password"]},
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        assert r.status_code in (301, 302)
        loc = r.headers.get("Location") or ""
        assert "/ui/select-site" not in loc
        assert loc.endswith("/ui/admin") or loc == "/ui/admin"
        with c.session_transaction() as s:
            assert s.get("site_id") == seeded["site_a"]


def test_bound_admin_cannot_view_select_site(monkeypatch):
    db_url = _temp_db_url()
    app = create_app({"TESTING": True, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    with app.app_context():
        db = get_session()
        seeded = _seed_bound_admin(db)
        c = app.test_client()
        # Login first to establish session
        c.post(
            "/auth/login",
            data={"email": seeded["email"], "password": seeded["password"]},
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        r = c.get("/ui/select-site", follow_redirects=False)
        assert r.status_code in (301, 302)
        loc = r.headers.get("Location") or ""
        assert loc.endswith("/ui/admin") or loc == "/ui/admin"


def test_bound_admin_cannot_switch_site_via_selector_post(monkeypatch):
    db_url = _temp_db_url()
    app = create_app({"TESTING": True, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    with app.app_context():
        db = get_session()
        seeded = _seed_bound_admin(db)
        c = app.test_client()
        c.post(
            "/auth/login",
            data={"email": seeded["email"], "password": seeded["password"]},
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        with c.session_transaction() as s:
            assert s.get("site_id") == seeded["site_a"]
            assert s.get("site_lock") is True
        # Attempt to switch to site_b should be forbidden
        r = c.post("/ui/select-site", data={"site_id": seeded["site_b"], "next": "/ui/admin"}, follow_redirects=False)
        assert r.status_code == 403
        # Session remains bound to site_a
        with c.session_transaction() as s:
            assert s.get("site_id") == seeded["site_a"]
