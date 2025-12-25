from __future__ import annotations

"""Purge all tenants and tenant-scoped data except tenants used by superusers.

Usage (PowerShell):
  py -3.12 .\scripts\purge_all_tenants_except_superuser.py

This will:
- Identify tenant_ids for users with role='superuser' and keep those tenants
- Delete tenant-scoped rows from common tables for all other tenants
- Delete users for those tenants (keeps superusers)
- Delete remaining tenants (non-kept)

Designed for local/dev SQLite; safe on Postgres if run carefully.
"""

import os
import sys
sys.path.append(os.getcwd())

from sqlalchemy import text
from core import create_app
from core.db import get_session


def table_exists(conn, table: str) -> bool:
    try:
        if conn.bind.dialect.name == "sqlite":
            row = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table}).fetchone()
            return bool(row)
        row = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"), {"t": table}).fetchone()
        return bool(row)
    except Exception:
        return False


def main() -> int:
    app = create_app({"TESTING": True})
    removed_counts: dict[str, int] = {}
    with app.app_context():
        db = get_session()
        try:
            conn = db.connection()
            keep_tenants: set[int] = set()
            if table_exists(conn, "users"):
                rows = conn.execute(text("SELECT DISTINCT tenant_id FROM users WHERE role='superuser'"))
                keep_tenants = {int(r[0]) for r in rows.fetchall() if r[0] is not None}
            # Collect tenants to delete
            to_delete: set[int] = set()
            if table_exists(conn, "tenants"):
                rows = conn.execute(text("SELECT id FROM tenants")).fetchall()
                for r in rows:
                    tid = int(r[0])
                    if tid not in keep_tenants:
                        to_delete.add(tid)
            if not to_delete:
                print("No tenants to delete (or only superuser tenants exist).")
                return 0
            # Helper to delete from tables with tenant_id
            def del_from(table: str) -> None:
                if not table_exists(conn, table):
                    return
                # Build IN list safely
                ids = ",".join(str(t) for t in sorted(to_delete))
                sql = f"DELETE FROM {table} WHERE tenant_id IN ({ids})"
                res = conn.execute(text(sql))
                removed_counts[table] = res.rowcount or 0
            # Child tables first (partial list; add as needed)
            child_tables = [
                "menu_variants",
                "task_status_transitions",
                "unit_diet_assignments",
                "menu_overrides",
                "notes",
                "tasks",
                "menus",
                "attendance",
                "recipes",
                "dishes",
                "messages",
                "service_metrics",
                "portion_guidelines",
                "shift_slots",
                "shift_templates",
                "tenant_feature_flags",
                "tenant_metadata",
                "units",
            ]
            for tbl in child_tables:
                del_from(tbl)
            # Users for those tenants, excluding superusers
            if table_exists(conn, "users"):
                ids = ",".join(str(t) for t in sorted(to_delete))
                res = conn.execute(text(f"DELETE FROM users WHERE tenant_id IN ({ids}) AND (role IS NULL OR role!='superuser')"))
                removed_counts["users"] = res.rowcount or 0
            # Finally remove tenants
            if table_exists(conn, "tenants"):
                ids = ",".join(str(t) for t in sorted(to_delete))
                res = conn.execute(text(f"DELETE FROM tenants WHERE id IN ({ids})"))
                removed_counts["tenants"] = res.rowcount or 0
            db.commit()
        finally:
            db.close()
    print("Tenant purge complete. Rows removed:")
    for k in sorted(removed_counts.keys()):
        print(f"  {k}: {removed_counts[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
