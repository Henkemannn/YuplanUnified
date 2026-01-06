from __future__ import annotations
from typing import Optional
from datetime import date as _date

from core.weekview.service import WeekviewService
from core.meal_registration_repo import MealRegistrationRepo
from core.db import get_session
from sqlalchemy import text

from viewmodels.portal.department_week_vm import DepartmentWeekViewModel, DepartmentDayVM, DepartmentDaySelectionVM


def build_department_week_vm(tenant_id: int, year: int, week: int, department_id: str, site_id: Optional[str] = None) -> DepartmentWeekViewModel:
    svc = WeekviewService()
    payload, _etag = svc.fetch_weekview(tenant_id, year, week, department_id)
    summaries = payload.get("department_summaries") or []
    dep = summaries[0] if summaries else {}
    days = dep.get("days") or []

    # Resolve department/site names and residents base
    db = get_session()
    try:
        row_d = db.execute(text("SELECT name, resident_count_fixed, site_id FROM departments WHERE id=:i"), {"i": department_id}).fetchone()
        department_name = row_d[0] if row_d else "Avdelning"
        residents = int(row_d[1] or 0) if row_d else 0
        site_id = site_id or (row_d[2] if row_d else None)
    finally:
        db.close()

    # Registrations for completion per day
    reg_repo = MealRegistrationRepo()
    try:
        reg_repo.ensure_table_exists()
        regs = reg_repo.get_registrations_for_week(tenant_id, site_id or "", department_id, year, week)
    except Exception:
        regs = []
    reg_map = {(r["date"], r["meal_type"]): bool(r.get("registered")) for r in regs}

    day_vms = []
    any_menu = False
    missing_choice_days = []
    for idx, d in enumerate(days, start=1):
        date_str = d.get("date")
        weekday_name = d.get("weekday_name")
        mt = d.get("menu_texts") or {}
        lunch = mt.get("lunch") or {}
        dinner = mt.get("dinner") or {}
        any_menu = any_menu or bool(lunch.get("alt1") or lunch.get("alt2") or dinner.get("alt1") or dinner.get("alt2"))
        lunch_registered = reg_map.get((date_str, "lunch"), False)
        alt2_marked = bool(d.get("alt2_lunch"))
        # Simple completion rule: lunch registered OR explicit choice present (alt2 flag as proxy)
        is_complete = bool(lunch_registered or alt2_marked)
        if (weekday_name in ("Måndag","Tisdag","Onsdag","Torsdag","Fredag")) and not is_complete:
            missing_choice_days.append(weekday_name)
        day_vms.append(
            DepartmentDayVM(
                index=idx,
                name=weekday_name,
                date=date_str,
                lunch_alt1=lunch.get("alt1"),
                lunch_alt2=lunch.get("alt2"),
                dinner=dinner.get("alt1") or dinner.get("alt2"),
                alt2_marked=alt2_marked,
                is_complete=is_complete,
            )
        )

    if not days:
        # Synthesize placeholder days Mon–Sun
        base_monday = _date.fromisocalendar(year, week, 1)
        names = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]
        for i, nm in enumerate(names):
            d = base_monday + __import__("datetime").timedelta(days=i)
            day_vms.append(DepartmentDayVM(index=i+1, name=nm, date=d.isoformat()))

    if not any_menu:
        status_text = "Ingen meny"
    elif len(missing_choice_days) == 0:
        status_text = "Veckan är klar"
    else:
        status_text = "Veckan är inte klar"

    return DepartmentWeekViewModel(
        week=week,
        year=year,
        department_name=department_name,
        department_id=int(department_id) if str(department_id).isdigit() else 0,
        residents=residents,
        status_text=status_text,
        days=day_vms,
    )


def build_department_day_selection_vm(
    tenant_id: int,
    year: int,
    week: int,
    department_id: int,
    site_id: Optional[str],
    day_index: int,
) -> DepartmentDaySelectionVM:
    """
    Build DepartmentDaySelectionVM by leveraging the week VM and picking a single day.
    """
    week_vm = build_department_week_vm(
        tenant_id=tenant_id,
        year=year,
        week=week,
        department_id=str(department_id),
        site_id=site_id,
    )
    # Guard index
    try:
        day = next((d for d in week_vm.days if int(getattr(d, "index", 0)) == int(day_index)), None)
    except Exception:
        day = None
    if not day:
        # Synthesize minimal day
        from datetime import date as _d
        iso_date = _d.fromisocalendar(year, week, max(1, min(7, day_index))).isoformat()
        return DepartmentDaySelectionVM(
            year=year,
            week=week,
            department_id=department_id,
            department_name=week_vm.department_name,
            day_index=day_index,
            date=iso_date,
            day_name=["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"][day_index-1],
            lunch_alt1=None,
            lunch_alt2=None,
            dinner=None,
            alt2_selected=False,
            is_complete=False,
        )
    return DepartmentDaySelectionVM(
        year=year,
        week=week,
        department_id=department_id,
        department_name=week_vm.department_name,
        day_index=day_index,
        date=day.date,
        day_name=day.name,
        lunch_alt1=day.lunch_alt1,
        lunch_alt2=day.lunch_alt2,
        dinner=day.dinner,
        alt2_selected=bool(getattr(day, "alt2_marked", False)),
        is_complete=bool(getattr(day, "is_complete", False)),
    )


def set_department_lunch_choice_alt2(
    tenant_id: int,
    site_id: str,
    year: int,
    week: int,
    department_id: int,
    day_index: int,
    alt2_selected: bool,
) -> None:
    """
    Persist Alt2 lunch choice for a specific department/day using existing Alt2Repo.
    Reuses the same keys (site_id, department_id, week, weekday) as Weekview enrichment.
    """
    from core.admin_repo import Alt2Repo
    repo = Alt2Repo()
    # Alt2Repo.bulk_upsert expects items with site_id, department_id, week, weekday, enabled
    items = [{
        "site_id": str(site_id),
        "department_id": str(department_id),
        "week": int(week),
        "weekday": int(day_index),
        "enabled": bool(alt2_selected),
    }]
    try:
        repo.bulk_upsert(items)
    except Exception:
        # For scaffolding step, swallow errors; later we can surface flash messages
        pass
