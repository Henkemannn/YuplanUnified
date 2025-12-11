from __future__ import annotations

from datetime import date as _date

from sqlalchemy import text

from .db import get_session
from .residents_weekly_repo import ResidentsWeeklyRepo


def get_effective_residents_for_week(department_id: str, year: int, week: int) -> dict:
    """
    Returns a dict like:
    {
        "resident_count_fixed": int,
        "residents_lunch": int,   # override or fixed
        "residents_dinner": int,  # override or fixed
        "has_override": bool
    }
    """
    db = get_session()
    try:
        # Read fixed from departments
        row = db.execute(
            text(
                "SELECT COALESCE(resident_count_fixed, 0) FROM departments WHERE id=:id"
            ),
            {"id": department_id},
        ).fetchone()
        fixed = int(row[0] or 0) if row else 0
    finally:
        db.close()

    repo = ResidentsWeeklyRepo()
    ov = repo.get_for_week(department_id, year, week)
    if ov:
        lunch = ov["residents_lunch"] if ov["residents_lunch"] is not None else fixed
        dinner = ov["residents_dinner"] if ov["residents_dinner"] is not None else fixed
        return {
            "resident_count_fixed": fixed,
            "residents_lunch": int(lunch),
            "residents_dinner": int(dinner),
            "has_override": True,
        }
    else:
        return {
            "resident_count_fixed": fixed,
            "residents_lunch": fixed,
            "residents_dinner": fixed,
            "has_override": False,
        }
