from __future__ import annotations

from datetime import date as _date

import pytest
from sqlalchemy import event

from core.admin_repo import (
    DepartmentDietOverridesRepo,
    DepartmentsRepo,
    DietDefaultsRepo,
    DietTypesRepo,
    SitesRepo,
)
from core.etag import ConcurrencyError
from core.weekview.service import WeekviewService
from core.db import get_session


def _canonical_diet_id(site_id: str, name: str, *, default_select: bool) -> int:
    row = next(row for row in DietTypesRepo().list_all(site_id=site_id) if row["name"] == name)
    assert row["semantics"] == "atomic"
    assert row["requirement_key"]
    if bool(row["default_select"]) != default_select:
        DietTypesRepo().update(int(row["id"]), default_select=default_select)
        row = next(row for row in DietTypesRepo().list_all(site_id=site_id) if row["name"] == name)
    assert bool(row["default_select"]) is default_select
    return int(row["id"])


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


def test_stale_diet_default_update_rolls_back(app_session):
    site, _ = SitesRepo().create_site("Stale diet defaults site")
    departments = DepartmentsRepo()
    department, initial_version = departments.create_department(
        site_id=site["id"], name="Stale diet defaults", resident_count_mode="fixed", resident_count_fixed=8
    )
    diet_id = _canonical_diet_id(site["id"], "Laktosfri", default_select=False)
    current_version = departments.upsert_department_diet_defaults(
        department["id"], initial_version, [{"diet_type_id": str(diet_id), "default_count": 2}]
    )

    with pytest.raises(ConcurrencyError):
        departments.upsert_department_diet_defaults(
            department["id"], initial_version, [{"diet_type_id": str(diet_id), "default_count": 5}]
        )

    assert departments.get_version(department["id"]) == current_version
    defaults = DietDefaultsRepo().list_for_department(department["id"])
    assert [(str(row["diet_type_id"]), row["default_count"]) for row in defaults] == [(str(diet_id), 2)]


def test_diet_default_update_does_not_run_runtime_ddl(app_session):
    site, _ = SitesRepo().create_site("Diet defaults runtime DDL site")
    departments = DepartmentsRepo()
    department, version = departments.create_department(
        site_id=site["id"], name="Diet defaults runtime DDL", resident_count_mode="fixed", resident_count_fixed=8
    )
    diet_id = _canonical_diet_id(site["id"], "Laktosfri", default_select=False)
    session = get_session()
    engine = session.get_bind()
    session.close()
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        departments.upsert_department_diet_defaults(
            department["id"], version, [{"diet_type_id": str(diet_id), "default_count": 2}]
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert not [
        statement for statement in statements
        if statement.lstrip().split(None, 1)[0].upper() in {"CREATE", "ALTER", "DROP"}
    ]


def test_weekview_applies_department_diet_overrides_and_falls_back(app_session):
    site, _ = SitesRepo().create_site("Override Site")
    dep, dep_v = DepartmentsRepo().create_department(
        site_id=site["id"],
        name="Avd Override",
        resident_count_mode="fixed",
        resident_count_fixed=12,
    )
    diet_id = _canonical_diet_id(site["id"], "Laktosfri", default_select=False)
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
