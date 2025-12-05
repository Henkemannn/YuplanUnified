from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Dict

from .db import get_session
from sqlalchemy import text


@dataclass
class CookDashboardVM:
    site_id: str
    site_name: str
    date: _date
    iso_year: int
    iso_week: int

    menu_today: Dict[str, str]
    total_residents_today: int
    total_specials_today: int
    total_normal_today: int

    links: Dict[str, str]


class CookDashboardService:
    def get_view(self, tenant_id: int, site_id: str, today: _date | None = None) -> CookDashboardVM:
        d = today or _date.today()
        iso = d.isocalendar()
        year, week = int(iso[0]), int(iso[1])

        db = get_session()
        try:
            row = db.execute(text("SELECT name FROM sites WHERE id=:i"), {"i": site_id}).fetchone()
            site_name = row[0] if row else site_id
        finally:
            db.close()

        menu_today = {
            "lunch_alt1": "",
            "lunch_alt2": "",
            "dinner": "",
            "dessert": "",
        }

        total_residents_today = 0
        total_specials_today = 0
        total_normal_today = 0

        links = {
            "kitchen_grid": f"/ui/portal/week?site_id={site_id}&show_kost_grid=1&year={year}&week={week}",
            "planera_week": f"/ui/planera/week?site_id={site_id}&year={year}&week={week}&date={d.isoformat()}&meal=lunch",
            "planera_day": f"/ui/planera/day?ui=unified&site_id={site_id}&date={d.isoformat()}&meal=lunch",
            "week_report": f"/ui/reports/weekly?site_id={site_id}&year={year}&week={week}",
        }

        return CookDashboardVM(
            site_id=site_id,
            site_name=site_name,
            date=d,
            iso_year=year,
            iso_week=week,
            menu_today=menu_today,
            total_residents_today=total_residents_today,
            total_specials_today=total_specials_today,
            total_normal_today=total_normal_today,
            links=links,
        )
