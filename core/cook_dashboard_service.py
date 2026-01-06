from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import List, Dict, Any

from .weekview.service import WeekviewService
from .meal_registration_repo import MealRegistrationRepo
from .db import get_session
from sqlalchemy import text
from flask import url_for


@dataclass
class CookDashboardDepartmentVM:
    name: str
    residents_lunch: int
    residents_dinner: int
    specials_lunch: int
    specials_dinner: int
    alt2_today: bool
    planera_lunch_url: str
    planera_dinner_url: str
    veckovy_url: str
    report_url: str


@dataclass
class CookDashboardSiteVM:
    site_name: str
    departments: List[CookDashboardDepartmentVM]


@dataclass
class CookDashboardMealVM:
    name: str
    totals_normalkost: int
    totals_specials: int
    alt2_count: int | None
    status: str  # "done" | "partial" | "not_done"


@dataclass
class CookDashboardVM:
    date: _date
    weekday_name: str
    meals: List[CookDashboardMealVM]
    sites: List[CookDashboardSiteVM]
    department_portal_status: List["DepartmentPortalStatusVM"]


@dataclass
class DepartmentPortalStatusVM:
    department_id: int
    department_name: str
    week: int
    is_complete: bool
    completed_days: int
    total_days: int
    year: int


class CookDashboardService:
    def get_view(self, tenant_id: int, site_id: str | None, today: _date) -> CookDashboardVM:
        svc = WeekviewService()
        iso = today.isocalendar()
        year, week = iso[0], iso[1]

        # No fallback: callers must provide active site explicitly
        if not site_id:
            return CookDashboardVM(departments=[], site_name="", week=week, year=year)

        # Departments for site
        db = get_session()
        try:
            deps = db.execute(text("SELECT id, name FROM departments WHERE site_id=:s ORDER BY name"), {"s": site_id}).fetchall()
            departments = [{"id": str(d[0]), "name": str(d[1] or "")} for d in deps]
            site_name_row = db.execute(text("SELECT name FROM sites WHERE id=:s"), {"s": site_id}).fetchone()
            site_name = str(site_name_row[0] or "") if site_name_row else ""
        finally:
            db.close()

        # Registrations table may be absent; ignore errors
        reg_repo = MealRegistrationRepo()
        try:
            reg_repo.ensure_table_exists()
        except Exception:
            pass

        total_norm_lunch = 0
        total_spec_lunch = 0
        total_norm_dinner = 0
        total_spec_dinner = 0
        alt2_count_today = 0
        lunch_done_count = 0
        dinner_done_count = 0

        site_vm = CookDashboardSiteVM(site_name=site_name, departments=[])
        for dep in departments:
            payload, _etag = svc.fetch_weekview(tenant_id, year, week, dep_id:=dep["id"])  # type: ignore[name-defined]
            summaries = payload.get("department_summaries") or []
            days = summaries[0].get("days") if summaries else []
            today_entry = next((d for d in days if d.get("date") == today.isoformat()), None)
            residents = (today_entry.get("residents") if today_entry else {}) or {}
            menu_texts = (today_entry.get("menu_texts") if today_entry else {}) or {}
            alt2 = False
            try:
                alt2 = bool(menu_texts.get("lunch", {}).get("alt2"))
            except Exception:
                alt2 = False

            rl = int(residents.get("lunch", 0) or 0)
            rd = int(residents.get("dinner", 0) or 0)
            specials_lunch = int((today_entry.get("specials", {}) or {}).get("lunch", 0)) if today_entry else 0
            specials_dinner = int((today_entry.get("specials", {}) or {}).get("dinner", 0)) if today_entry else 0

            total_norm_lunch += max(0, rl - specials_lunch)
            total_spec_lunch += specials_lunch
            total_norm_dinner += max(0, rd - specials_dinner)
            total_spec_dinner += specials_dinner
            if alt2:
                alt2_count_today += 1

            # Build URLs via url_for
            planera_lunch_url = url_for(
                "ui.planera_day_ui_v2",
                ui="unified",
                date=today.isoformat(),
                meal="lunch",
                site_id=site_id,
                department_id=dep_id,
            )
            planera_dinner_url = url_for(
                "ui.planera_day_ui_v2",
                ui="unified",
                date=today.isoformat(),
                meal="dinner",
                site_id=site_id,
                department_id=dep_id,
            )
            iso = today.isocalendar()
            year, week = iso[0], iso[1]
            veckovy_url = url_for(
                "ui.kitchen_veckovy_week",
                site_id=site_id,
                department_id=dep_id,
                year=year,
                week=week,
            )
            report_url = url_for(
                "ui.weekview_report_ui",
                site_id=site_id,
                year=year,
                week=week,
            )

            # Simple meal completion heuristics: done when specials recorded
            if specials_lunch > 0 or rl > 0:
                lunch_done_count += 1
            if specials_dinner > 0 or rd > 0:
                dinner_done_count += 1

            dep_vm = CookDashboardDepartmentVM(
                name=dep["name"],
                residents_lunch=rl,
                residents_dinner=rd,
                specials_lunch=specials_lunch,
                specials_dinner=specials_dinner,
                alt2_today=alt2,
                planera_lunch_url=planera_lunch_url,
                planera_dinner_url=planera_dinner_url,
                veckovy_url=veckovy_url,
                report_url=report_url,
            )
            site_vm.departments.append(dep_vm)

        # Compute meal status across departments
        dep_count = len(site_vm.departments)
        def status_for(done_count: int) -> str:
            if dep_count == 0:
                return "not_done"
            if done_count >= dep_count:
                return "done"
            if done_count > 0:
                return "partial"
            return "not_done"

        meals = [
            CookDashboardMealVM(
                name="Lunch",
                totals_normalkost=total_norm_lunch,
                totals_specials=total_spec_lunch,
                alt2_count=alt2_count_today,
                status=status_for(lunch_done_count),
            ),
            CookDashboardMealVM(
                name="Kvällsmat",
                totals_normalkost=total_norm_dinner,
                totals_specials=total_spec_dinner,
                alt2_count=None,
                status=status_for(dinner_done_count),
            ),
        ]

        day_names = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
        weekday_name = day_names[today.isoweekday() - 1]
        # Build portal status list for this site/week
        dept_status_list: List[DepartmentPortalStatusVM] = []
        if site_id:
            try:
                from views.portal_department_week import build_department_week_vm
                # list departments again (already available as `departments`)
                for dep in departments:
                    week_vm = build_department_week_vm(tenant_id=tenant_id, year=year, week=week, department_id=dep["id"], site_id=site_id)
                    total_days = len(week_vm.days)
                    completed_days = sum(1 for d in week_vm.days if getattr(d, "is_complete", False))
                    is_complete = (total_days > 0 and completed_days == total_days)
                    dept_status_list.append(
                        DepartmentPortalStatusVM(
                            department_id=int(dep["id"]) if str(dep["id"]).isdigit() else 0,
                            department_name=dep["name"],
                            week=week,
                            is_complete=is_complete,
                            completed_days=completed_days,
                            total_days=total_days,
                            year=year,
                        )
                    )
            except Exception:
                dept_status_list = []

        vm = CookDashboardVM(date=today, weekday_name=weekday_name, meals=meals, sites=[site_vm], department_portal_status=dept_status_list)
        return vm
