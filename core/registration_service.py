from __future__ import annotations

from typing import Any
from datetime import date as _date

from .db import get_session
from .ui_blueprint import get_meal_labels_for_site  # reuse labels
from .admin_repo import DietDefaultsRepo
from .weekview.repo import WeekviewRepo


class RegistrationService:
    def get_day_meal_view(self, tenant_id: int, site_id: str, department_id: str, date_str: str, meal: str) -> dict[str, Any]:
        meal_labels = get_meal_labels_for_site(site_id) if site_id else {"lunch": "Lunch", "dinner": "Kväll"}
        weekday_name = self._weekday_name(date_str)
        meal_name = meal_labels.get("lunch" if meal == "lunch" else "dinner")
        residents = self._get_residents(site_id, department_id, date_str, meal)

        # Compute year/week/day for marks/etag context
        try:
            d = _date.fromisoformat(date_str)
            iso = d.isocalendar()
            year, week, day_of_week = int(iso[0]), int(iso[1]), int(iso[2])
        except Exception:
            year, week, day_of_week = (0, 0, 0)

        # Planned defaults and mark state
        planned_map = self._get_planned_defaults(department_id)
        marks_set = self._get_marks_set(tenant_id, department_id, year, week, day_of_week, meal)
        diet_rows = self._get_diet_rows(site_id, department_id, date_str, meal, planned_map, marks_set)

        # Phase 1 totals remain based on special_count to keep tests stable
        total_special = sum(int(r.get("special_count") or 0) for r in diet_rows)
        normal_count = max(int(residents) - int(total_special), 0)
        is_complete = residents >= 0 and (int(residents) == int(total_special) + int(normal_count))

        # Optional Phase 2 metric for later reports
        marked_special_count = sum((int(r.get("planned_count") or 0) if r.get("is_marked") else 0) for r in diet_rows)
        return {
            "site_id": site_id,
            "department_id": department_id,
            "date": date_str,
            "weekday_name": weekday_name,
            "meal": meal,
            "meal_name": meal_name,
            "residents": int(residents),
            "total_special": int(total_special),
            "normal_count": int(normal_count),
            "is_complete": bool(is_complete),
            "diet_rows": diet_rows,
            "marked_special_count": int(marked_special_count),
        }

    def _weekday_name(self, date_str: str) -> str:
        try:
            import datetime
            d = datetime.date.fromisoformat(date_str)
            # Map ISO weekday to Swedish names
            names = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
            return names[d.isoweekday() - 1]
        except Exception:
            return ""

    def _get_residents(self, site_id: str, department_id: str, date_str: str, meal: str) -> int:
        db = get_session()
        try:
            col = "lunch" if meal == "lunch" else "dinner"
            try:
                row = db.execute(
                    __import__("sqlalchemy").text(
                        f"SELECT {col} FROM residents_counts WHERE site_id=:s AND department_id=:d AND date=:dt"
                    ),
                    {"s": site_id, "d": department_id, "dt": date_str},
                ).fetchone()
                return int(row[0]) if row and row[0] is not None else 0
            except Exception:
                return 0
        finally:
            db.close()

    def _get_diet_rows(self, site_id: str, department_id: str, date_str: str, meal: str, planned_map: dict[str, int], marks_set: set[tuple[str, str]]) -> list[dict[str, Any]]:
        db = get_session()
        try:
            # Fetch all diet types; if table missing, return empty
            try:
                diet_types = db.execute(__import__("sqlalchemy").text("SELECT id, name, is_default FROM diet_types"))
                types = [(str(r[0]), str(r[1]), bool(r[2]) if len(r) > 2 else False) for r in diet_types.fetchall()]
            except Exception:
                types = []
            # Sum registrations per type for given context; if table missing, no registrations
            try:
                regs = db.execute(
                    __import__("sqlalchemy").text(
                        "SELECT diet_type_id, SUM(count) FROM diet_registrations WHERE site_id=:s AND department_id=:d AND date=:dt AND meal=:m GROUP BY diet_type_id"
                    ),
                    {"s": site_id, "d": department_id, "dt": date_str, "m": meal},
                ).fetchall()
                reg_map = {str(r[0]): int(r[1] or 0) for r in regs}
            except Exception:
                reg_map = {}
            rows: list[dict[str, Any]] = []
            for dt_id, dt_name, is_default in types:
                planned = int(planned_map.get(dt_id, 0))
                is_marked = (meal, dt_id) in marks_set
                rows.append({
                    "diet_type_id": dt_id,
                    "name": dt_name,
                    "is_default": is_default,
                    # Phase 1 registered count (kept for totals/tests)
                    "special_count": reg_map.get(dt_id, 0),
                    # Phase 2 planned defaults and mark state for UI
                    "planned_count": planned,
                    "is_marked": bool(is_marked),
                })
            return rows
        finally:
            db.close()

    def _get_planned_defaults(self, department_id: str) -> dict[str, int]:
        try:
            repo = DietDefaultsRepo()
            items = repo.list_for_department(department_id)
            return {str(it["diet_type_id"]): int(it.get("default_count", 0)) for it in items}
        except Exception:
            return {}

    def _get_marks_set(self, tenant_id: int, department_id: str, year: int, week: int, day_of_week: int, meal: str) -> set[tuple[str, str]]:
        """Return set of (meal, diet_type_id) that are marked for given day.

        Uses WeekviewRepo to read raw marks for the week, then filters by day/meal.
        """
        try:
            repo = WeekviewRepo()
            payload = repo.get_weekview(tenant_id, year, week, department_id)
            summaries = payload.get("department_summaries") or []
            marks = (summaries[0].get("marks") if summaries else []) or []
            out: set[tuple[str, str]] = set()
            for m in marks:
                try:
                    if int(m.get("day_of_week")) == int(day_of_week) and bool(m.get("marked")) and str(m.get("meal")) in ("lunch", "dinner"):
                        out.add((str(m.get("meal")), str(m.get("diet_type"))))
                except Exception:
                    continue
            return out
        except Exception:
            return set()