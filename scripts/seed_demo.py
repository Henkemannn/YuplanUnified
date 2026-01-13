"""Seed minimal demo data: site + department + weekview placeholders.

Run: python scripts/seed_demo.py

Creates rows only if they are absent. Safe for repeats.
"""
from __future__ import annotations

from sqlalchemy import text
import sys
from pathlib import Path

# Ensure project root (parent of scripts/) is on sys.path when run as a file.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from core.app_factory import create_app
from core.db import get_session

SITE_ID = "site-demo-1"
DEPARTMENT_ID = "dept-demo-1"


def main() -> None:
    app = create_app()
    # Use app context if any services rely on it later.
    with app.app_context():
        db = get_session()
        try:
            # Sites table (might be in migrations; ensure exists)
            db.execute(text("""
            CREATE TABLE IF NOT EXISTS sites (
              id VARCHAR(64) PRIMARY KEY,
              name VARCHAR(120) NOT NULL
            )"""))
            db.execute(text("""
            CREATE TABLE IF NOT EXISTS departments (
              id VARCHAR(64) PRIMARY KEY,
              site_id VARCHAR(64) NOT NULL,
              name VARCHAR(120) NOT NULL,
              FOREIGN KEY(site_id) REFERENCES sites(id)
            )"""))
            # Minimal presence for department_notes table referenced in portal service
            db.execute(text("""
            CREATE TABLE IF NOT EXISTS department_notes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              department_id VARCHAR(64) NOT NULL,
              notes TEXT,
              FOREIGN KEY(department_id) REFERENCES departments(id)
            )"""))
            # Insert site if missing
            if not db.execute(text("SELECT 1 FROM sites WHERE id=:id"), {"id": SITE_ID}).fetchone():
                db.execute(text("INSERT INTO sites(id, name) VALUES (:id, :name)"), {"id": SITE_ID, "name": "Demo Site"})
            # Insert department if missing
            if not db.execute(text("SELECT 1 FROM departments WHERE id=:id"), {"id": DEPARTMENT_ID}).fetchone():
                db.execute(text("INSERT INTO departments(id, site_id, name) VALUES (:id, :site_id, :name)"), {"id": DEPARTMENT_ID, "site_id": SITE_ID, "name": "Demo Department"})
            db.commit()
            print("Demo seed complete. Department:", DEPARTMENT_ID)
            print("Visit: http://127.0.0.1:8000/ui/portal/department/week?demo=1 (after starting app)")
        finally:
            db.close()


if __name__ == "__main__":
    main()
