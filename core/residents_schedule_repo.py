from __future__ import annotations

from typing import Optional, Sequence
from sqlalchemy import text
from .db import get_session


class ResidentsScheduleRepo:
    """CRUD for per-day residents variation.

    Table: department_residents_schedule
      department_id TEXT NOT NULL
      week INTEGER NULL  -- when NULL => forever schedule
      weekday INTEGER NOT NULL  -- 1..7 ISO
      meal TEXT NOT NULL  -- 'lunch' | 'dinner'
      count INTEGER NOT NULL
      PRIMARY KEY(department_id, week, weekday, meal)
    """

    def _ensure_table(self) -> None:
        db = get_session()
        try:
            db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS department_residents_schedule (
                        department_id TEXT NOT NULL,
                        week INTEGER,
                        weekday INTEGER NOT NULL,
                        meal TEXT NOT NULL,
                        count INTEGER NOT NULL,
                        PRIMARY KEY(department_id, week, weekday, meal)
                    )
                    """
                )
            )
            db.commit()
        finally:
            db.close()

    def get_week(self, department_id: str, week: int) -> list[dict]:
        self._ensure_table()
        db = get_session()
        try:
            rows = db.execute(
                text(
                    "SELECT weekday, meal, count FROM department_residents_schedule WHERE department_id=:d AND week=:w ORDER BY weekday, meal"
                ),
                {"d": department_id, "w": int(week)},
            ).fetchall()
            return [{"weekday": int(r[0]), "meal": str(r[1]), "count": int(r[2])} for r in rows]
        finally:
            db.close()

    def get_forever(self, department_id: str) -> list[dict]:
        self._ensure_table()
        db = get_session()
        try:
            rows = db.execute(
                text(
                    "SELECT weekday, meal, count FROM department_residents_schedule WHERE department_id=:d AND week IS NULL ORDER BY weekday, meal"
                ),
                {"d": department_id},
            ).fetchall()
            return [{"weekday": int(r[0]), "meal": str(r[1]), "count": int(r[2])} for r in rows]
        finally:
            db.close()

    def upsert_items(self, department_id: str, week: Optional[int], items: Sequence[dict]) -> None:
        self._ensure_table()
        db = get_session()
        try:
            for it in items:
                db.execute(
                    text(
                        """
                        INSERT INTO department_residents_schedule(department_id, week, weekday, meal, count)
                        VALUES(:d, :w, :wd, :m, :c)
                        ON CONFLICT(department_id, week, weekday, meal)
                        DO UPDATE SET count=excluded.count
                        """
                    ),
                    {"d": department_id, "w": week, "wd": int(it["weekday"]), "m": str(it["meal"]), "c": int(it["count"])},
                )
            db.commit()
        finally:
            db.close()

    def delete_week(self, department_id: str, week: int) -> None:
        self._ensure_table()
        db = get_session()
        try:
            db.execute(text("DELETE FROM department_residents_schedule WHERE department_id=:d AND week=:w"), {"d": department_id, "w": int(week)})
            db.commit()
        finally:
            db.close()

    def delete_forever(self, department_id: str) -> None:
        self._ensure_table()
        db = get_session()
        try:
            db.execute(text("DELETE FROM department_residents_schedule WHERE department_id=:d AND week IS NULL"), {"d": department_id})
            db.commit()
        finally:
            db.close()