from __future__ import annotations

import os
import sys
from typing import Optional

from sqlalchemy import text

# Ensure project root on sys.path for local script execution
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.config import Config
from core.db import init_engine, get_session
from core.models import Tenant
from core.auth import generate_password_hash as app_hash
from core.app_factory import create_app


def _effective_db_url() -> tuple[str, Optional[str]]:
    cfg = Config.from_env()
    env_url = os.getenv("DATABASE_URL")
    url = cfg.database_url
    sqlite_file = None
    if not env_url and str(url).startswith("sqlite///"):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        inst = os.path.join(root, "instance")
        os.makedirs(inst, exist_ok=True)
        sqlite_file = os.path.join(inst, "dev.db")
        url = f"sqlite:///{sqlite_file}"
    elif str(url).startswith("sqlite///"):
        sqlite_file = os.path.abspath(url.replace("sqlite:///", "", 1))
    return url, sqlite_file


def _ensure_users_site_id_column(db) -> None:
    try:
        # Add users.site_id if missing (sqlite fallback only; Postgres path also handled)
        has_site_id = False
        try:
            rows = db.execute(text("PRAGMA table_info('users')")).fetchall()
            has_site_id = any(str(r[1]) == "site_id" for r in rows)
        except Exception:
            # Postgres
            chk = db.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='site_id'"))
            has_site_id = chk.fetchone() is not None
        if not has_site_id:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT NULL"))
                db.commit()
            except Exception:
                db.rollback()
    except Exception:
        pass


def main() -> int:
    url, sqlite_file = _effective_db_url()
    print(f"Using DATABASE_URL={url}")
    if sqlite_file:
        print(f"SQLite file: {sqlite_file}")

    init_engine(url)
    db = get_session()
    try:
        # Ensure minimal tables exist (tenants/users)
        try:
            # Touch users table to see if exists
            db.execute(text("SELECT 1 FROM users LIMIT 1"))
        except Exception:
            # Create via ORM metadata
            from core.db import create_all
            create_all()

        # Tenant: reuse first or create one
        t = db.query(Tenant).first()
        if not t:
            t = Tenant(name="Primary")
            db.add(t)
            db.flush()

        # Ensure sites table exists and seed one site
        try:
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sites (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 0,
                        notes TEXT NULL,
                        updated_at TEXT
                    )
                    """
                )
            )
        except Exception:
            pass
        # Create or reuse first site
        row = db.execute(text("SELECT id FROM sites ORDER BY id LIMIT 1")).fetchone()
        if not row:
            import uuid
            sid = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:id,:name,0)"), {"id": sid, "name": "Dev Site"})
        else:
            sid = str(row[0])

        # Ensure users.site_id column exists (for sqlite dev fallback)
        _ensure_users_site_id_column(db)

        # Upsert admin user
        email = "admin@dev.local"
        pw_hash = app_hash("pass123")
        urow = db.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": email.lower()}).fetchone()
        if not urow:
            db.execute(
                text(
                    "INSERT INTO users(tenant_id, email, password_hash, role, is_active) "
                    "VALUES(:tenant_id, :email, :ph, 'admin', 1)"
                ),
                {"tenant_id": t.id, "email": email.lower(), "ph": pw_hash},
            )
            uid = int(db.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": email.lower()}).fetchone()[0])
        else:
            uid = int(urow[0])
            # Refresh password to known value for local dev
            db.execute(text("UPDATE users SET password_hash=:ph WHERE id=:id"), {"ph": pw_hash, "id": uid})

        # Bind site_id on the user (column added above if necessary)
        try:
            db.execute(text("UPDATE users SET site_id = :sid WHERE id = :id"), {"sid": sid, "id": uid})
        except Exception:
            pass

        db.commit()
        print("Seed complete.")
        print(f"  Tenant id={t.id}")
        print(f"  Site id={sid}")
        print("  Admin user: email=admin@dev.local password=pass123 (role=admin)")

    finally:
        db.close()

    # Optional: quick login smoke with Flask test client
    try:
        app = create_app({"TESTING": True, "database_url": url})
        with app.test_client() as c:
            r = c.post("/auth/login", json={"email": "admin@dev.local", "password": "pass123"})
            print(f"/auth/login status={r.status_code}")
            try:
                print(f"/auth/login json={r.get_json()}")
            except Exception:
                print("/auth/login returned non-JSON response")
    except Exception as e:
        print(f"Login smoke skipped due to error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
