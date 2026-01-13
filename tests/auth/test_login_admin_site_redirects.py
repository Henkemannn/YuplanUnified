import uuid
from flask import session as _session
from core.app_factory import create_app
import os
from core.db import get_session
from werkzeug.security import generate_password_hash
from sqlalchemy import text


def _ensure_min_schema(db):
    # Minimal schema for in-memory SQLite to satisfy ORM queries in /auth/login
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
    # Include tenant_id to allow tenant-scoped site counting in login HTML flow
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version INTEGER DEFAULT 0,
            tenant_id INTEGER
        )
    """))
    db.commit()


def _seed_tenant_and_admin(db, sites_count=1):
    # Ensure minimal schema exists for in-memory DBs
    _ensure_min_schema(db)
    # Create tenant and admin user via raw SQL to avoid ORM metadata create_all
    tenant_id = 1
    db.execute(text("INSERT OR REPLACE INTO tenants(id, name, active) VALUES(:i, :n, 1)"), {"i": tenant_id, "n": "Primary"})
    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Passw0rd!"
    db.execute(
        text(
            "INSERT INTO users(tenant_id, email, password_hash, role, is_active) VALUES(:t, :e, :p, 'admin', 1)"
        ),
        {"t": tenant_id, "e": email.lower(), "p": generate_password_hash(pw)},
    )
    # Reset and seed sites table for this tenant to ensure deterministic counts
    try:
        db.execute(text("DELETE FROM sites WHERE tenant_id = :t"), {"t": tenant_id})
    except Exception:
        pass
    # Seed sites table
    for i in range(sites_count):
        sid = f"s_{uuid.uuid4().hex[:8]}"
        db.execute(
            text("INSERT OR REPLACE INTO sites(id,name,version,tenant_id) VALUES(:i,:n,0,:t)"),
            {"i": sid, "n": f"Site {i+1}", "t": tenant_id},
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
    # Dummy object with email attribute for test client
    class _U:
        pass
    u = _U()
    u.email = email
    return {"id": tenant_id, "name": "Primary"}, u, pw


def _temp_db_url():
    fname = f"test_{uuid.uuid4().hex}.db"
    base = os.path.abspath(os.path.join(os.getcwd()))
    return f"sqlite:///{os.path.join(base, fname)}"


def test_admin_login_two_sites_redirects_to_selector(monkeypatch):
    db_url = _temp_db_url()
    app = create_app({"TESTING": True, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    with app.app_context():
        db = get_session()
        tenant, user, pw = _seed_tenant_and_admin(db, sites_count=2)
        # Prefer tenant-scoped count to avoid interference from any global bootstrap
        cnt_t = db.execute(text("SELECT COUNT(1) FROM sites WHERE tenant_id=:t"), {"t": tenant["id"]}).fetchone()[0]
        assert int(cnt_t) == 2
        c = app.test_client()
        r = c.post("/auth/login", data={"email": user.email, "password": pw}, headers={"Accept": "text/html"}, follow_redirects=False)
        assert r.status_code in (301, 302)
        loc = r.headers.get("Location") or ""
        assert "/ui/select-site" in loc
        assert "next=" in loc and ("/ui/admin" in loc or "%2Fui%2Fadmin" in loc)
        # Ensure site_id not set in session yet
        with c.session_transaction() as s:
            assert not s.get("site_id")


def test_admin_login_single_site_sets_site_and_redirects_to_admin(monkeypatch):
    db_url = _temp_db_url()
    app = create_app({"TESTING": True, "database_url": db_url, "SQLALCHEMY_DATABASE_URI": db_url})
    with app.app_context():
        db = get_session()
        tenant, user, pw = _seed_tenant_and_admin(db, sites_count=1)
        cnt_t = db.execute(text("SELECT COUNT(1) FROM sites WHERE tenant_id=:t"), {"t": tenant["id"]}).fetchone()[0]
        assert int(cnt_t) == 1
        c = app.test_client()
        r = c.post("/auth/login", data={"email": user.email, "password": pw}, headers={"Accept": "text/html"}, follow_redirects=False)
        assert r.status_code in (301, 302)
        loc = r.headers.get("Location") or ""
        assert "/ui/select-site" not in loc
        assert loc.endswith("/ui/admin") or loc == "/ui/admin"
        # Session should include site_id and version
        with c.session_transaction() as s:
            assert s.get("site_id")
            assert s.get("site_context_version")
