from __future__ import annotations

import sys
import os

sys.path.append(os.getcwd())

from core import create_app
from core.db import get_session
from sqlalchemy import text

# Ensure app + engine init and stable dev DB path
app = create_app({"TESTING": True})


def _ensure_weekview_schema() -> None:
    # Import locally to avoid heavy imports at module level
    try:
        from core.weekview.repo import WeekviewRepo

        WeekviewRepo()._ensure_schema()
    except Exception:
        # Best-effort: if tables don't exist, deletes below are guarded
        pass


def _table_exists(db, name: str) -> bool:
    try:
        # Works for SQLite; Postgres path uses information_schema
        if db.bind and db.bind.dialect and db.bind.dialect.name == "sqlite":
            row = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name}).fetchone()
            return bool(row)
        else:
            row = db.execute(
                text(
                    "SELECT to_regclass(:n)"
                ),
                {"n": name},
            ).fetchone()
            return bool(row and row[0])
    except Exception:
        return False


def main() -> int:
    db = get_session()
    try:
        _ensure_weekview_schema()
        # Find DebugSite
        # Guard if sites table missing
        if not _table_exists(db, "sites"):
            print("No sites table; nothing to cleanup.")
            return 0
        row = db.execute(text("SELECT id FROM sites WHERE name=:n"), {"n": "DebugSite"}).fetchone()
        if not row:
            print("No DebugSite found; nothing to cleanup.")
            return 0
        sid = str(row[0])
        # Collect departments under that site (guard table existence)
        if not _table_exists(db, "departments"):
            print("No departments table; removing site only.")
            db.execute(text("DELETE FROM sites WHERE id=:s"), {"s": sid})
            db.commit()
            print("Cleanup done (site only).")
            return 0
        deps = [str(r[0]) for r in db.execute(text("SELECT id FROM departments WHERE site_id=:s"), {"s": sid}).fetchall()]
        print(f"Cleaning DebugSite id={sid}, departments={len(deps)}")
        # Delete weekview data for those departments (guard tables and delete per-department to avoid SQL injection/expansion issues)
        weekview_tables = (
            "weekview_registrations",
            "weekview_versions",
            "weekview_residents_count",
            "weekview_alt2_flags",
        )
        for t in weekview_tables:
            if deps and _table_exists(db, t):
                for d in deps:
                    db.execute(text(f"DELETE FROM {t} WHERE department_id=:d"), {"d": d})
        # Department diet defaults
        if deps and _table_exists(db, "department_diet_defaults"):
            for d in deps:
                db.execute(text("DELETE FROM department_diet_defaults WHERE department_id=:d"), {"d": d})
        # Delete departments
        db.execute(text("DELETE FROM departments WHERE site_id=:s"), {"s": sid})
        # Finally delete site
        db.execute(text("DELETE FROM sites WHERE id=:s"), {"s": sid})
        db.commit()
        print("Cleanup done.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
