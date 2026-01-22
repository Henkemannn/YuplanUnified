from __future__ import annotations

import os
import sys
from typing import Optional

from sqlalchemy import text

# Ensure project root on sys.path for local script execution
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Local imports from app
from core.config import Config
from core.db import init_engine, get_session


def _effective_db_url() -> tuple[str, Optional[str]]:
    """Return the effective DATABASE_URL the app would use and sqlite file path if any.

    Mirrors core.app_factory's behavior of resolving sqlite:///dev.db into
    an absolute path under the instance/ directory when DATABASE_URL is not set.
    """
    cfg = Config.from_env()
    env_url = os.getenv("DATABASE_URL")
    url = cfg.database_url
    sqlite_file = None
    if not env_url and str(url).startswith("sqlite///"):
        # Resolve to instance/dev.db relative to repo root
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        inst = os.path.join(root, "instance")
        os.makedirs(inst, exist_ok=True)
        sqlite_file = os.path.join(inst, "dev.db")
        url = f"sqlite:///{sqlite_file}"
    elif str(url).startswith("sqlite///"):
        sqlite_file = os.path.abspath(url.replace("sqlite:///", "", 1))
    return url, sqlite_file


def _has_column(db, table: str, col: str) -> bool:
    try:
        if db.bind and db.bind.dialect and db.bind.dialect.name == "sqlite":
            rows = db.execute(text("PRAGMA table_info(:t)"), {"t": table}).fetchall()
            # Some sqlite drivers don't bind table names; fallback without param
            if not rows:
                rows = db.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
            return any(str(r[1]) == col for r in rows)
        # Postgres / others
        chk = db.execute(
            text(
                "SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c"
            ),
            {"t": table, "c": col},
        )
        return chk.fetchone() is not None
    except Exception:
        return False


def main() -> int:
    url, sqlite_file = _effective_db_url()
    print(f"Effective DATABASE_URL: {url}")
    if sqlite_file:
        print(f"SQLite file: {sqlite_file}")

    # Initialize engine and open session
    init_engine(url)
    db = get_session()
    try:
        # Check users table presence
        users_exist = False
        try:
            # Lightweight detection
            db.execute(text("SELECT 1 FROM users LIMIT 1"))
            users_exist = True
        except Exception:
            users_exist = False

        if not users_exist:
            print("Users table not found in this database.")
            return 0

        # Determine usable columns
        cols = ["id", "email", "role", "tenant_id"]
        if _has_column(db, "users", "site_id"):
            cols.append("site_id")
        else:
            cols.append("NULL AS site_id")
        col_sql = ", ".join(cols)
        rows = db.execute(text(f"SELECT {col_sql} FROM users ORDER BY id"))
        rows = rows.fetchall()

        if not rows:
            print("? Inga användare finns i databasen")
            print("Diagnos: Inga users → databasen är tom.")
            return 0

        print("? Användare i databasen:")
        for r in rows:
            # r may be a Row object; access by index
            rid, email, role, tenant_id, site_id = (
                r[0],
                r[1],
                r[2],
                r[3],
                r[4] if len(r) > 4 else None,
            )
            print(f"- id={rid} email={email} role={role} tenant_id={tenant_id} site_id={site_id}")

        # Basic diagnosis for site binding
        # If any non-superuser lacks site_id and tenant seems to have >1 sites, warn
        multi_site_hint = None
        try:
            has_tenant_on_sites = _has_column(db, "sites", "tenant_id")
            if has_tenant_on_sites:
                # Check per-tenant site counts
                t_counts = {}
                for r in rows:
                    t = r[3]
                    if t is None:
                        continue
                    if t in t_counts:
                        continue
                    cnt = db.execute(text("SELECT COUNT(*) FROM sites WHERE tenant_id=:t"), {"t": t}).fetchone()[0]
                    t_counts[t] = int(cnt)
                offenders = [r for r in rows if (r[2] != "superuser" and r[4] in (None, "") and t_counts.get(r[3], 0) > 1)]
                if offenders:
                    emails = ", ".join([str(r[1]) for r in offenders])
                    multi_site_hint = f"Diagnos: {emails} saknar site_id och tenant har fler än en site → login blockas av strict site binding."
            else:
                # No tenant_id on sites table; auth cannot auto-bind a single site under sqlite fallback
                offenders = [r for r in rows if (r[2] != "superuser" and (r[4] in (None, "")))]
                if offenders:
                    emails = ", ".join([str(r[1]) for r in offenders])
                    multi_site_hint = (
                        "Diagnos: sites saknar tenant-kolumn; användare utan site_id kan blockeras av strict site binding."
                        f" Påverkade konton: {emails}"
                    )
        except Exception:
            pass

        if multi_site_hint:
            print(multi_site_hint)

        print("Obs: Om login svarar 'invalid credentials' trots att user finns → sannolikt fel hash/seed.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
