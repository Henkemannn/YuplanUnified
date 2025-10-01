from __future__ import annotations

from datetime import date
from typing import Any

from .db import get_session
from .models import Attendance


class AttendanceService:
    """Service for recording and summarizing attendance.

    Methods:
      set_attendance(unit_id, day_date, meal, count, origin='manual')
      summary(unit_id, week_dates) -> list per date/meal or aggregated future variant
    """
    def __init__(self):
        pass

    def set_attendance(self, unit_id: int, day_date: date, meal: str, count: int, origin: str = "manual") -> int:
        meal = meal.strip()
        db = get_session()
        try:
            row: Attendance | None = db.query(Attendance).filter_by(unit_id=unit_id, date=day_date, meal=meal).first()
            if row is not None:
                row.count = count
                row.origin = origin
            else:
                row = Attendance(unit_id=unit_id, date=day_date, meal=meal, count=count, origin=origin)
                db.add(row)
            db.commit()
            assert row is not None
            return row.id
        finally:
            db.close()

    def summary(self, unit_id: int, start: date, end: date) -> dict[str, Any]:
        db = get_session()
        try:
            q = db.query(Attendance).filter(Attendance.unit_id==unit_id, Attendance.date>=start, Attendance.date<=end)
            items = []
            for a in q.order_by(Attendance.date, Attendance.meal).all():
                items.append({
                    "date": a.date.isoformat(),
                    "meal": a.meal,
                    "count": a.count,
                    "origin": a.origin
                })
            return {"unit_id": unit_id, "items": items}
        finally:
            db.close()
