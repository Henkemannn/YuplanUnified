from __future__ import annotations

from datetime import date as _date

from core.admin_repo import (
    DepartmentDietOverridesRepo,
    DepartmentsRepo,
    DietTypesRepo,
    SitesRepo,
)
from core.weekview.service import WeekviewService


def _diet_entry(payload: dict, diet_type_id: str, day: int, meal: str) -> dict | None:
    summaries = payload.get("department_summaries") or []
    if not summaries:
        return None
    days = summaries[0].get("days") or []
    target_day = next((d for d in days if int(d.get("day_of_week") or 0) == day), None)
    if not target_day:
        return None
    rows = (((target_day.get("diets") or {}).get(meal)) or [])
    return next((r for r in rows if str(r.get("diet_type_id")) == str(diet_type_id)), None)


def test_weekview_applies_department_diet_overrides_and_falls_back(app_session):
    site, _ = SitesRepo().create_site("Override Site")
    dep, dep_v = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Override",
        resident_count_mode="fixed",
        resident_count_fixed=12,
    )
    diet_id = DietTypesRepo().create(site_id=site["id"], name="Laktosfri", default_select=False)
    new_v = DepartmentsRepo().upsert_department_diet_defaults(
        dept_id=dep["id"],
        expected_version=dep_v,
        items=[{"diet_type_id": str(diet_id), "default_count": 3}],
    )
    assert new_v >= dep_v

    DepartmentDietOverridesRepo().replace_for_department_diet(
        dept_id=dep["id"],
        diet_type_id=str(diet_id),
        items=[{"day": 1, "meal": "lunch", "count": 7}],
    )

    iso = _date.today().isocalendar()
    payload, _ = WeekviewService().fetch_weekview(
        tenant_id=1,
        year=int(iso[0]),
        week=int(iso[1]),
        department_id=dep["id"],
        site_id=site["id"],
    )

    monday_lunch = _diet_entry(payload, str(diet_id), day=1, meal="lunch")
    monday_dinner = _diet_entry(payload, str(diet_id), day=1, meal="dinner")
    assert monday_lunch is not None
    assert monday_dinner is not None
    assert int(monday_lunch.get("resident_count") or 0) == 7
    assert int(monday_lunch.get("planned_count") or 0) == 7
    assert int(monday_lunch.get("base_count") or 0) == 3
    assert bool(monday_lunch.get("has_override")) is True
    assert int(monday_dinner.get("resident_count") or 0) == 3
    assert bool(monday_dinner.get("has_override")) is False

    DepartmentDietOverridesRepo().replace_for_department_diet(
        dept_id=dep["id"],
        diet_type_id=str(diet_id),
        items=[],
    )
    payload2, _ = WeekviewService().fetch_weekview(
        tenant_id=1,
        year=int(iso[0]),
        week=int(iso[1]),
        department_id=dep["id"],
        site_id=site["id"],
    )
    monday_lunch2 = _diet_entry(payload2, str(diet_id), day=1, meal="lunch")
    assert monday_lunch2 is not None
    assert int(monday_lunch2.get("resident_count") or 0) == 3
    assert bool(monday_lunch2.get("has_override")) is False
