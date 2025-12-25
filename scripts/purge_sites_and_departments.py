from __future__ import annotations

import os
import sys
sys.path.append(os.getcwd())

from sqlalchemy import text
from core import create_app
from core.db import get_session


def main() -> int:
    app = create_app({"TESTING": True})
    with app.app_context():
        db = get_session()
        try:
            removed = {}
            def try_del(sql: str, label: str) -> None:
                try:
                    res = db.execute(text(sql))
                    removed[label] = res.rowcount if res.rowcount is not None else 0
                except Exception:
                    removed[label] = removed.get(label, 0)
            # Child tables first (ignore if not present)
            try_del("DELETE FROM department_diet_defaults", "department_diet_defaults")
            # Specialkost types (tenant-scoped) — full purge for clean slate
            try_del("DELETE FROM dietary_types", "dietary_types")
            try_del("DELETE FROM weekview_registrations", "weekview_registrations")
            try_del("DELETE FROM weekview_residents_count", "weekview_residents_count")
            try_del("DELETE FROM weekview_alt2_flags", "weekview_alt2_flags")
            # Parents
            try_del("DELETE FROM departments", "departments")
            try_del("DELETE FROM sites", "sites")
            db.commit()
            print("Purge done. Rows removed:")
            for k in sorted(removed.keys()):
                print(f"  {k}: {removed[k]}")
        finally:
            db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
