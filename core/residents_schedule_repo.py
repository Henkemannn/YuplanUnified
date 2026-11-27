from __future__ import annotations

from typing import Optional, Sequence
from sqlalchemy import text
from .db import get_session


def upsert_schedule_items_in_session(db, department_id: str, week: Optional[int], items: Sequence[dict]) -> None:
    conflict = (
        "(department_id, weekday, meal) WHERE week IS NULL"
        if week is None
        else "(department_id, week, weekday, meal) WHERE week IS NOT NULL"
    )
    statement = text(
        "INSERT INTO department_residents_schedule(department_id, week, weekday, meal, count) "
        "VALUES(:d, :w, :wd, :m, :c) "
        f"ON CONFLICT {conflict} DO UPDATE SET count=excluded.count"
    )
    for item in items:
        db.execute(statement, {
            "d": department_id, "w": week, "wd": int(item["weekday"]),
            "m": str(item["meal"]), "c": int(item["count"]),
        })


class ResidentsScheduleRepo:
    """CRUD for per-day residents variation.

    Table: department_residents_schedule
      department_id TEXT NOT NULL
      week INTEGER NULL  -- when NULL => forever schedule
      weekday INTEGER NOT NULL  -- 1..7 ISO
      meal TEXT NOT NULL  -- 'lunch' | 'dinner'
      count INTEGER NOT NULL
      Separate unique keys for weekly and forever rows.
    """

    def get_week(self, department_id: str, week: int) -> list[dict]:
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
        db = get_session()
        try:
            upsert_schedule_items_in_session(db, department_id, week, items)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_week(self, department_id: str, week: int) -> None:
        db = get_session()
        try:
            db.execute(text("DELETE FROM department_residents_schedule WHERE department_id=:d AND week=:w"), {"d": department_id, "w": int(week)})
            db.commit()
        finally:
            db.close()

    def delete_forever(self, department_id: str) -> None:
        db = get_session()
        try:
            db.execute(text("DELETE FROM department_residents_schedule WHERE department_id=:d AND week IS NULL"), {"d": department_id})
            db.commit()
        finally:
            db.close()