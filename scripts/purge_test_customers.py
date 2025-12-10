from __future__ import annotations

"""Purge all test customers (sites) and related admin data, and optionally users.

Usage (PowerShell):
  # Ensure your virtualenv is active and DB is the dev DB
  py -3.12 scripts/purge_test_customers.py

This removes rows from core admin tables and many tenant-scoped tables to give a clean slate.
By default, tenants and users stay intact; use --include-users to remove all non-superuser users.
"""

import sys
import os
from typing import Sequence
from sqlalchemy import text

from core import create_app
from core.db import get_session


def table_exists(conn, table: str) -> bool:
    try:
        if conn.bind.dialect.name == "sqlite":
            row = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table}).fetchone()
            return bool(row)
        # Generic check
        row = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"), {"t": table}).fetchone()
        return bool(row)
    except Exception:
        return False


def _delete_tables(conn, tables: Sequence[str], removed_counts: dict[str, int]) -> None:
    for tbl in tables:
        if table_exists(conn, tbl):
            try:
                res = conn.execute(text(f"DELETE FROM {tbl}"))
                removed_counts[tbl] = res.rowcount if res.rowcount is not None else 0
            except Exception:
                removed_counts[tbl] = removed_counts.get(tbl, 0)


def main() -> int:
    app = create_app()
    removed_counts: dict[str, int] = {}
    include_users = "--include-users" in sys.argv
    include_tenant_data = True  # always clear tenant-scoped domain data
    superuser_email = os.getenv("SUPERUSER_EMAIL", "Henrik.Jonsson@Yuplan.se").lower()
    with app.app_context():
        db = get_session()
        try:
            conn = db.connection()
            # Child-first order to avoid basic FK issues
            child_tables = [
                "menu_variants",
                "task_status_transitions",
                "unit_diet_assignments",
                "menu_overrides",
                "department_diet_defaults",
                "alt2_flags",
                "weekview_alt2_flags",
                "weekview_items",
            ]
            parent_tables = [
                "menus",
                "tasks",
                "attendance",
                "recipes",
                "dishes",
                "messages",
                "service_metrics",
                "portion_guidelines",
                "shift_slots",
                "shift_templates",
                "notes",
                "tenant_feature_flags",
                "tenant_metadata",
                "departments",
                "sites",
                "units",
            ]

            _delete_tables(conn, child_tables, removed_counts)
            _delete_tables(conn, parent_tables, removed_counts)

            # Optionally delete non-superuser users
            if include_users and table_exists(conn, "users"):
                try:
                    res = conn.execute(
                        text(
                            "DELETE FROM users WHERE LOWER(email) != :su AND (role IS NULL OR role != 'superuser')"
                        ),
                        {"su": superuser_email},
                    )
                    removed_counts["users"] = res.rowcount or 0
                except Exception:
                    removed_counts["users"] = removed_counts.get("users", 0)
            db.commit()
        finally:
            db.close()
    # Summary
    print("Purge complete. Rows removed:")
    for k in sorted(removed_counts.keys()):
        print(f"  {k}: {removed_counts[k]}")
    if include_users:
        print("Users: non-superuser accounts removed; kept:", superuser_email)
    else:
        print("Users: kept (pass --include-users to remove non-superusers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
