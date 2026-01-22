from __future__ import annotations

import os
import sys
import uuid
from typing import Optional

from sqlalchemy import text

# Ensure project root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.config import Config
from core.db import init_engine, get_session
from core.app_factory import create_app


def _effective_db_url() -> tuple[str, Optional[str]]:
    cfg = Config.from_env()
    env_url = os.getenv("DATABASE_URL")
    url = cfg.database_url
    sqlite_file = None
    if not env_url and str(url).startswith("sqlite///"):
        inst = os.path.join(ROOT, "instance")
        os.makedirs(inst, exist_ok=True)
        sqlite_file = os.path.join(inst, "dev.db")
        url = f"sqlite:///{sqlite_file}"
    elif str(url).startswith("sqlite///"):
        sqlite_file = os.path.abspath(url.replace("sqlite:///", "", 1))
    return url, sqlite_file


def _has_column(db, table: str, col: str) -> bool:
    try:
        if db.bind and db.bind.dialect and db.bind.dialect.name == "sqlite":
            rows = db.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
            return any(str(r[1]) == col for r in rows)
        chk = db.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c"), {"t": table, "c": col})
        return chk.fetchone() is not None
    except Exception:
        return False


def main() -> int:
    url, sqlite_file = _effective_db_url()
    print(f"Patching local DB for site binding…\nDATABASE_URL={url}")
    if sqlite_file:
        print(f"SQLite file: {sqlite_file}")

    init_engine(url)
    db = get_session()
    try:
        # Ensure sites table exists (SQLite fallback)
        db.execute(text(
            """
            CREATE TABLE IF NOT EXISTS sites (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                notes TEXT NULL,
                updated_at TEXT
            )
            """
        ))

        # Ensure sites.tenant_id exists
        if not _has_column(db, "sites", "tenant_id"):
            try:
                db.execute(text("ALTER TABLE sites ADD COLUMN tenant_id INTEGER NULL"))
                print("Added column sites.tenant_id")
            except Exception as e:
                print(f"Warning: failed to add sites.tenant_id: {e}")

        # Ensure users.site_id exists
        if not _has_column(db, "users", "site_id"):
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN site_id TEXT NULL"))
                print("Added column users.site_id")
            except Exception as e:
                print(f"Warning: failed to add users.site_id: {e}")

        # Locate admin user
        admin_email = "admin@dev.local"
        u = db.execute(text("SELECT id, tenant_id FROM users WHERE LOWER(email)=:e"), {"e": admin_email.lower()}).fetchone()
        if not u:
            print("admin@dev.local not found. Run: python scripts/seed_login_dev.py")
            return 1
        admin_id = int(u[0])
        admin_tid = int(u[1]) if u[1] is not None else None
        if admin_tid is None:
            print("Admin user has no tenant_id; cannot bind site." )
            return 1

        # Pick (or create) a site to bind
        srow = db.execute(text("SELECT id FROM sites ORDER BY id LIMIT 1")).fetchone()
        if not srow:
            sid = str(uuid.uuid4())
            db.execute(text("INSERT INTO sites(id, name, version) VALUES(:id,:name,0)"), {"id": sid, "name": "Dev Site"})
            print(f"Created site id={sid}")
        else:
            sid = str(srow[0])

        # Set sites.tenant_id for chosen site
        try:
            db.execute(text("UPDATE sites SET tenant_id=:t WHERE id=:id"), {"t": admin_tid, "id": sid})
        except Exception as e:
            print(f"Warning: failed to set sites.tenant_id: {e}")
        # Ensure exactly ONE site belongs to this tenant for auto-binding to work
        try:
            db.execute(text("UPDATE sites SET tenant_id=NULL WHERE tenant_id=:t AND id!=:id"), {"t": admin_tid, "id": sid})
        except Exception as e:
            print(f"Warning: failed to isolate single site for tenant: {e}")

        # Bind admin to that site
        try:
            db.execute(text("UPDATE users SET site_id=:sid WHERE id=:id"), {"sid": sid, "id": admin_id})
        except Exception as e:
            print(f"Warning: failed to set users.site_id: {e}")

        db.commit()
        # Debug: show columns
        try:
            cols_sites = [r[1] for r in db.execute(text("PRAGMA table_info('sites')")).fetchall()]
        except Exception:
            cols_sites = []
        try:
            cols_users = [r[1] for r in db.execute(text("PRAGMA table_info('users')")).fetchall()]
        except Exception:
            cols_users = []
        print(f"Patched: sites.tenant_id set for site {sid}; admin@dev.local bound to site_id.")
        print("sites columns:", cols_sites)
        print("users columns:", cols_users)
    finally:
        db.close()

    # Quick verification: diagnose + login smoke
    try:
        from tools.diagnose_login import main as diag_main  # type: ignore
        print("\n--- Running diagnose_login ---")
        diag_main()
    except Exception:
        print("(diagnose_login run skipped)")

    try:
        app = create_app({"TESTING": True, "database_url": url})
        with app.test_client() as c:
            # Debug: check what SitesRepo reports
            try:
                from core.admin_repo import SitesRepo  # type: ignore
                sites = SitesRepo().list_sites_for_tenant(admin_tid)
                print("SitesRepo.list_sites_for_tenant:", sites)
                from core.context import get_single_site_id_for_tenant as one_site  # type: ignore
                print("get_single_site_id_for_tenant:", one_site(admin_tid))
            except Exception as e:
                print(f"SitesRepo debug failed: {e}")
            r = c.post("/auth/login", json={"email": "admin@dev.local", "password": "pass123"})
            print(f"/auth/login status={r.status_code}")
            try:
                print(f"/auth/login json={r.get_json()}")
            except Exception:
                print("/auth/login returned non-JSON response")
            # Inspect session
            with c.session_transaction() as sess:
                print("session keys:", list(sess.keys()))
                print("session tenant_id:", sess.get("tenant_id"))
                print("session site_id:", sess.get("site_id"))
                print("session site_lock:", sess.get("site_lock"))
    except Exception as e:
        print(f"Login smoke failed: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
