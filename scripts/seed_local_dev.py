from __future__ import annotations

"""Seed local dev database with a tenant, site, and admin users.

Usage (PowerShell):
  py -3.12 scripts/seed_local_dev.py

Behavior:
- Connects using the same config path as the app (via core.create_app + core.db.get_session).
- Idempotent: reuses existing tenant/site/user if found; does not overwrite passwords.
- For SQLite, enables lightweight bootstrap of admin tables if missing.
"""

import os
import sys
from typing import Optional

# Ensure workspace root imports
sys.path.append(os.getcwd())

from sqlalchemy import text

from core import create_app
from core.db import get_session
from core.auth import generate_password_hash as app_hash

TENANT_NAME = "Dev Tenant"
SITE_ID = "dev-site"
SITE_NAME = "Varberg Test"
ADMIN_EMAIL = "admin@dev.local"
ADMIN_PASSWORD = "admin123!"
SYSADMIN_EMAIL = os.getenv("SYSADMIN_EMAIL", "sysadmin@dev.local")
SYSADMIN_PASSWORD = os.getenv("SYSADMIN_PASSWORD", "admin123!")
STAFF_EMAIL = "staff@dev.local"
STAFF_PASSWORD = "admin123!"


def table_exists(conn, table: str) -> bool:
    try:
        engine = getattr(conn, "bind", conn)
        if engine.dialect.name == "sqlite":
            row = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table}).fetchone()
            return bool(row)
        # Generic check
        row = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"), {"t": table}).fetchone()
        return bool(row)
    except Exception:
        return False


def ensure_sqlite_bootstrap():
    # For local dev convenience: allow core.db to create admin tables if using SQLite.
    if os.getenv("DATABASE_URL", "sqlite:///dev.db").startswith("sqlite:"):
        os.environ.setdefault("YP_ENABLE_SQLITE_BOOTSTRAP", "1")


def main() -> int:
    ensure_sqlite_bootstrap()
    app = create_app()

    with app.app_context():
        db = get_session()
        try:
            conn = db.connection()
            try:
                dialect = getattr(conn, "bind", conn).dialect.name
            except Exception:
                dialect = db.get_bind().dialect.name

            # 1) Tenant
            row = conn.execute(text("SELECT id FROM tenants WHERE LOWER(name) = :n"), {"n": TENANT_NAME.lower()}).fetchone()
            if row:
                tenant_id = int(row[0])
                tenant_created = False
            else:
                res = conn.execute(text("INSERT INTO tenants(name, active) VALUES(:n, 1)"), {"n": TENANT_NAME})
                # SQLite returns last inserted row id; Postgres may require RETURNING but autoincrement int is fine to re-fetch
                row2 = conn.execute(text("SELECT id FROM tenants WHERE LOWER(name) = :n"), {"n": TENANT_NAME.lower()}).fetchone()
                tenant_id = int(row2[0]) if row2 else None
                tenant_created = True
            if tenant_id is None:
                raise RuntimeError("Failed to ensure tenant ID")

            # 2) Site (admin tables) — ensure tenant_id present and correct
            if not table_exists(conn, "sites"):
                print("WARN: 'sites' table missing. If using SQLite, core.db bootstrap should create it. Ensure YP_ENABLE_SQLITE_BOOTSTRAP=1.")
            # Detect tenant_id column presence (SQLite-safe)
            has_site_tenant_col = True
            try:
                engine = getattr(conn, "bind", conn)
                if engine.dialect.name == "sqlite":
                    cols = conn.execute(text("PRAGMA table_info('sites')")).fetchall()
                    names = {str(r[1]) for r in cols}
                    has_site_tenant_col = ("tenant_id" in names)
            except Exception:
                has_site_tenant_col = True

            site_row = None
            site_tenant_current: Optional[int] = None
            try:
                site_row = conn.execute(
                    text("SELECT id, tenant_id FROM sites WHERE id = :sid OR LOWER(name) = :sn"),
                    {"sid": SITE_ID, "sn": SITE_NAME.lower()},
                ).fetchone()
                if site_row and len(site_row) >= 2:
                    site_tenant_current = (int(site_row[1]) if site_row[1] is not None else None)
            except Exception:
                # Fallback if tenant_id column not available
                try:
                    site_row = conn.execute(
                        text("SELECT id, name FROM sites WHERE id = :sid OR LOWER(name) = :sn"),
                        {"sid": SITE_ID, "sn": SITE_NAME.lower()},
                    ).fetchone()
                except Exception:
                    site_row = None

            site_backfilled = False
            if site_row:
                site_id = str(site_row[0])
                site_created = False
                if has_site_tenant_col and (site_tenant_current is None or site_tenant_current != tenant_id):
                    try:
                        conn.execute(text("UPDATE sites SET tenant_id = :tid WHERE id = :sid"), {"tid": tenant_id, "sid": site_id})
                        site_backfilled = True
                    except Exception:
                        site_backfilled = False
            else:
                try:
                    if has_site_tenant_col:
                        conn.execute(text("INSERT INTO sites(id, name, tenant_id) VALUES(:sid, :sn, :tid)"), {"sid": SITE_ID, "sn": SITE_NAME, "tid": tenant_id})
                    else:
                        conn.execute(text("INSERT INTO sites(id, name) VALUES(:sid, :sn)"), {"sid": SITE_ID, "sn": SITE_NAME})
                    site_id = SITE_ID
                    site_created = True
                except Exception as e:
                    print(f"ERROR: failed to insert site: {e}")
                    site_id = SITE_ID
                    site_created = False

            # 3) Admin user (tenant_admin)
            user_row = conn.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": ADMIN_EMAIL.lower()}).fetchone()
            if user_row:
                admin_user_id = int(user_row[0])
                admin_created = False
            else:
                # Use the app's hashing helper
                pw_hash = app_hash(ADMIN_PASSWORD)
                params = {
                    "tenant_id": tenant_id,
                    "email": ADMIN_EMAIL.lower(),
                    "role": "admin",
                    "password_hash": pw_hash,
                }
                # is_active column may not exist on some DBs; set if present
                has_is_active = True
                try:
                    conn.execute(text("SELECT is_active FROM users LIMIT 1"))
                except Exception:
                    has_is_active = False
                if has_is_active:
                    params["is_active"] = 1
                    sql = text(
                        "INSERT INTO users(tenant_id, email, role, password_hash, is_active) "
                        "VALUES(:tenant_id, :email, :role, :password_hash, :is_active)"
                    )
                else:
                    sql = text(
                        "INSERT INTO users(tenant_id, email, role, password_hash) "
                        "VALUES(:tenant_id, :email, :role, :password_hash)"
                    )
                conn.execute(sql, params)
                admin_user_id = int(conn.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": ADMIN_EMAIL.lower()}).fetchone()[0])
                admin_created = True

            # 4) System admin (optional)
            sys_row = conn.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": SYSADMIN_EMAIL.lower()}).fetchone()
            if sys_row:
                sys_user_id = int(sys_row[0])
                sys_created = False
            else:
                pw_hash2 = app_hash(SYSADMIN_PASSWORD)
                params2 = {
                    "tenant_id": tenant_id,
                    "email": SYSADMIN_EMAIL.lower(),
                    "role": "superuser",
                    "password_hash": pw_hash2,
                }
                has_is_active2 = True
                try:
                    conn.execute(text("SELECT is_active FROM users LIMIT 1"))
                except Exception:
                    has_is_active2 = False
                if has_is_active2:
                    params2["is_active"] = 1
                    sql2 = text(
                        "INSERT INTO users(tenant_id, email, role, password_hash, is_active) "
                        "VALUES(:tenant_id, :email, :role, :password_hash, :is_active)"
                    )
                else:
                    sql2 = text(
                        "INSERT INTO users(tenant_id, email, role, password_hash) "
                        "VALUES(:tenant_id, :email, :role, :password_hash)"
                    )
                conn.execute(sql2, params2)
                sys_user_id = int(conn.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": SYSADMIN_EMAIL.lower()}).fetchone()[0])
                sys_created = True

            # 5) Staff/Cook user for Weekview UI
            staff_row = conn.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": STAFF_EMAIL.lower()}).fetchone()
            if staff_row:
                staff_user_id = int(staff_row[0])
                staff_created = False
            else:
                pw_hash3 = app_hash(STAFF_PASSWORD)
                params3 = {
                    "tenant_id": tenant_id,
                    "email": STAFF_EMAIL.lower(),
                    # SAFE_UI_ROLES does not include 'staff'; use 'cook' to permit Weekview access
                    "role": "cook",
                    "password_hash": pw_hash3,
                }
                has_is_active3 = True
                try:
                    conn.execute(text("SELECT is_active FROM users LIMIT 1"))
                except Exception:
                    has_is_active3 = False
                if has_is_active3:
                    params3["is_active"] = 1
                    sql3 = text(
                        "INSERT INTO users(tenant_id, email, role, password_hash, is_active) "
                        "VALUES(:tenant_id, :email, :role, :password_hash, :is_active)"
                    )
                else:
                    sql3 = text(
                        "INSERT INTO users(tenant_id, email, role, password_hash) "
                        "VALUES(:tenant_id, :email, :role, :password_hash)"
                    )
                conn.execute(sql3, params3)
                staff_user_id = int(conn.execute(text("SELECT id FROM users WHERE LOWER(email) = :e"), {"e": STAFF_EMAIL.lower()}).fetchone()[0])
                staff_created = True

            db.commit()
        finally:
            db.close()

    # Print summary
    print("Seed complete:")
    print(f"  tenant: name='{TENANT_NAME}', id={tenant_id} (created={tenant_created})")
    print(f"  site: id='{SITE_ID}', name='{SITE_NAME}' (created={site_created})")
    # Log site tenant assignment status
    try:
        print(f"  site tenant_id={tenant_id} (created={site_created}, backfilled={site_backfilled})")
    except Exception:
        pass
    print(f"  tenant admin: email='{ADMIN_EMAIL}', password='<hidden>' (created={admin_created})")
    print(f"  system admin: email='{SYSADMIN_EMAIL}', password='<hidden>' (created={sys_created})")
    print(f"  weekview staff/cook: email='{STAFF_EMAIL}', password='<hidden>' (created={staff_created})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
