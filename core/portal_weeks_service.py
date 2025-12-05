from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, timedelta
from typing import List

from core.weekview.service import WeekviewService
from core.admin_repo import Alt2Repo


@dataclass
class PortalWeekItemVM:
    year: int
    week: int
    label: str
    start_date: _date
    end_date: _date
    status: str  # "done" | "in_progress" | "not_started"
    is_future: bool
    is_current: bool


@dataclass
class PortalWeeksVM:
    site_name: str
    department_name: str
    items: List[PortalWeekItemVM]


class PortalWeeksOverviewService:
    def __init__(self) -> None:
        self.weekview = WeekviewService()
        self.alt2 = Alt2Repo()

    def get_department_weeks_overview(
        self,
        tenant_id: int | str,
        department_id: str,
        site_name: str,
        department_name: str,
        base_date: _date | None = None,
        span_weeks: int = 12,
    ) -> PortalWeeksVM:
        base = base_date or _date.today()
        cur_year, cur_week = base.isocalendar()[0], base.isocalendar()[1]
        items: List[PortalWeekItemVM] = []
        for i in range(span_weeks):
            d = base + timedelta(weeks=i)
            iso = d.isocalendar()
            year, week = iso[0], iso[1]
            week_start = _date.fromisocalendar(year, week, 1)
            week_end = _date.fromisocalendar(year, week, 7)
            # Fetch week payload to detect presence of data
            payload, _ = self.weekview.fetch_weekview(tenant_id, year, week, department_id)
            summaries = payload.get("department_summaries") or []
            dep = summaries[0] if summaries else {}
            # Any presence checks
            has_counts = bool((dep.get("residents_counts") or []))
            has_marks = bool((dep.get("marks") or []))
            has_menu = False
            try:
                days = dep.get("days") or []
                for day in days:
                    mt = day.get("menu_texts") or {}
                    if mt.get("lunch") or mt.get("dinner"):
                        has_menu = True
                        break
            except Exception:
                has_menu = False

            # Choice completeness (reuse Alt2Repo days as explicit choice proxy)
            choice_rows = self.alt2.list_for_department_week(department_id, week)
            chosen_days = {int(r.get("weekday") or 0) for r in choice_rows if 1 <= int(r.get("weekday") or 0) <= 7}
            weekdays = {1, 2, 3, 4, 5}
            done = weekdays.issubset(chosen_days)
            has_any = has_counts or has_marks or has_menu or bool(chosen_days)
            status = "done" if done else ("in_progress" if has_any else "not_started")

            items.append(
                PortalWeekItemVM(
                    year=year,
                    week=week,
                    label=f"Vecka {week}",
                    start_date=week_start,
                    end_date=week_end,
                    status=status,
                    is_future=week_start > base,
                    is_current=(year == cur_year and week == cur_week),
                )
            )

        return PortalWeeksVM(site_name=site_name, department_name=department_name, items=items)


__all__ = [
    "PortalWeeksOverviewService",
    "PortalWeeksVM",
    "PortalWeekItemVM",
]
