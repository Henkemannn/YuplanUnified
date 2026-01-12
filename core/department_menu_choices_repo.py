from __future__ import annotations

from typing import Dict
from datetime import datetime
from sqlalchemy import text

from .db import get_session


class DepartmentMenuChoicesRepo:
    """Persist per-department lunch Alt1/Alt2 choices per weekday.

    Schema (SQLite-first):
        department_menu_choices(
            site_id TEXT,
            department_id TEXT,
            year INTEGER,
            week INTEGER,
            day INTEGER,           -- 1..7 (Mon=1)
            lunch_choice TEXT,     -- 'alt1' or 'alt2'
            updated_at TEXT,
            version INTEGER DEFAULT 1,
            UNIQUE(site_id, department_id, year, week, day)
        )
    """

    def ensure_table_exists(self) -> None:
        db = get_session()
        try:
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS department_menu_choices (
                        site_id TEXT NOT NULL,
                        department_id TEXT NOT NULL,
                        year INTEGER NOT NULL,
                        week INTEGER NOT NULL,
                        day INTEGER NOT NULL,
                        lunch_choice TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        version INTEGER DEFAULT 1,
                        UNIQUE(site_id, department_id, year, week, day)
                    )
                    """
                )
            )
            db.commit()
        finally:
            db.close()

    def get_choices_for_week(self, site_id: str, department_id: str, year: int, week: int) -> Dict[int, str]:
        self.ensure_table_exists()
        db = get_session()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT day, lunch_choice FROM department_menu_choices
                    WHERE site_id=:s AND department_id=:d AND year=:y AND week=:w
                    ORDER BY day
                    """
                ),
                {"s": site_id, "d": department_id, "y": year, "w": week},
            ).fetchall()
            out: Dict[int, str] = {}
            for r in rows:
                out[int(r[0])] = str(r[1])
            return out
        finally:
            db.close()

    def upsert_choice(self, site_id: str, department_id: str, year: int, week: int, day: int, lunch_choice: str) -> None:
        self.ensure_table_exists()
        now = datetime.utcnow().isoformat(timespec="seconds")
        db = get_session()
        try:
            db.execute(
                text(
                    """
                    INSERT INTO department_menu_choices(site_id, department_id, year, week, day, lunch_choice, updated_at)
                    VALUES(:s,:d,:y,:w,:day,:c,:ts)
                    ON CONFLICT(site_id, department_id, year, week, day)
                    DO UPDATE SET lunch_choice=excluded.lunch_choice, updated_at=excluded.updated_at
                    """
                ),
                {"s": site_id, "d": department_id, "y": year, "w": week, "day": day, "c": lunch_choice, "ts": now},
            )
            db.commit()
        finally:
            db.close()
