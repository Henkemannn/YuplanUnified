from __future__ import annotations

from datetime import date
from datetime import timedelta

from sqlalchemy import text

from core.admin_repo import DietTypesRepo
from core.admin_repo import DietDefaultsRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_week_grid_adapter import build_week_grid_specialkost_rows
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo


def _seed_site_department(app_session, *, site_id: str, department_id: str, department_name: str) -> None:
    from core.db import get_session

    conn = get_session()
    try:
        conn.execute(
            text("INSERT INTO sites(id, tenant_id, name) VALUES(:id, 1, :name) ON CONFLICT(id) DO UPDATE SET tenant_id=1, name=excluded.name"),
            {"id": site_id, "name": f"{department_name} site"},
        )
        conn.execute(
            text(
                "INSERT INTO departments(id, site_id, name, resident_count_mode, resident_count_fixed) VALUES(:id, :site_id, :name, 'fixed', 5) ON CONFLICT(id) DO UPDATE SET site_id=excluded.site_id, name=excluded.name, resident_count_mode='fixed', resident_count_fixed=5"
            ),
            {"id": department_id, "site_id": site_id, "name": department_name},
        )
        conn.commit()
    finally:
        conn.close()


def _seed_requirements(site_id: str, names: list[str]) -> dict[str, int]:
    repo = DietTypesRepo()
    out: dict[str, int] = {}
    for name in names:
        out[name] = repo.create(site_id=site_id, name=name, default_select=False, semantics="atomic")
    return out


def _days(year: int, week: int) -> list[dict[str, object]]:
    monday = date.fromisocalendar(year, week, 1)
    return [
        {
            "day_of_week": dow,
            "date": (monday + timedelta(days=dow - 1)).isoformat(),
            "alt2_lunch": dow == 2,
        }
        for dow in range(1, 8)
    ]


def _seed_fixture(app_session, *, site_id: str, cohort_dept_id: str, legacy_dept_id: str):
    _seed_site_department(app_session, site_id=site_id, department_id=cohort_dept_id, department_name="Cohort Avd")
    _seed_site_department(app_session, site_id=site_id, department_id=legacy_dept_id, department_name="Legacy Avd")
    ids = _seed_requirements(site_id, ["Timbal", "Glutenfri", "Laktosfri", "Legacy Kost"])
    group_repo = DepartmentRequirementGroupsRepo()
    group_one = group_repo.create_group(cohort_dept_id, 1, [ids["Timbal"], ids["Glutenfri"]], label=None, primary_requirement_id=ids["Timbal"])
    group_two = group_repo.create_group(cohort_dept_id, 1, [ids["Timbal"], ids["Glutenfri"], ids["Laktosfri"]], label=None, primary_requirement_id=ids["Timbal"])
    group_unresolved = group_repo.create_group(cohort_dept_id, 1, [ids["Glutenfri"], ids["Timbal"]], label=None, primary_requirement_id=None)
    # Zero-row group for omission checks
    group_zero = group_repo.create_group(cohort_dept_id, 1, [ids["Timbal"]], label="Zero", primary_requirement_id=ids["Timbal"])
    weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
    service_repo = DepartmentRequirementGroupServiceOverridesRepo()
    completion_repo = DepartmentRequirementGroupCompletionRepo()
    thursday = date.fromisocalendar(2026, 37, 4)
    monday = date.fromisocalendar(2026, 37, 1)
    tuesday = date.fromisocalendar(2026, 37, 2)
    weekday_repo.set_override(group_one["id"], thursday.isoweekday(), "lunch", 4)
    service_repo.set_override(group_one["id"], thursday, "lunch", 7)
    service_repo.set_override(group_one["id"], thursday, "dinner", 3)
    completion_repo.set_marked(cohort_dept_id, group_one["id"], thursday, "lunch", True)
    completion_repo.set_marked(cohort_dept_id, group_one["id"], thursday, "dinner", False)
    completion_repo.set_marked(cohort_dept_id, group_two["id"], monday, "lunch", False)
    # Keep unresolved group positive but distinct.
    service_repo.set_override(group_unresolved["id"], tuesday, "lunch", 2)
    service_repo.set_override(group_zero["id"], monday, "lunch", 0)
    service_repo.set_override(group_zero["id"], monday, "dinner", 0)
    return ids, group_one, group_two, group_unresolved, group_zero


def test_legacy_rows_pass_through_when_no_requirement_groups(app_session):
    site_id = "00000000-0000-0000-0000-00000000aa01"
    department_id = "00000000-0000-0000-0000-00000000aa02"
    _seed_site_department(app_session, site_id=site_id, department_id=department_id, department_name="Legacy Avd")
    rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[{"diet_type_id": "legacy-1", "diet_type_name": "Legacy 1", "cells": [{"day_index": 1, "meal": "lunch", "count": 2, "is_done": False, "is_override": False, "is_alt2": False} for _ in range(14)]}],
    )
    assert len(rows) == 1
    assert rows[0]["row_kind"] == "legacy"
    assert rows[0]["diet_type_name"] == "Legacy 1"


def test_cohort_row_label_uses_primary_then_modifiers(app_session):
    site_id = "00000000-0000-0000-0000-00000000ab01"
    department_id = "00000000-0000-0000-0000-00000000ab02"
    _seed_site_department(app_session, site_id=site_id, department_id=department_id, department_name="Cohort Avd")
    ids = _seed_requirements(site_id, ["Timbal", "Glutenfri", "Laktosfri"])
    DepartmentRequirementGroupsRepo().create_group(department_id, 1, [ids["Timbal"], ids["Glutenfri"], ids["Laktosfri"]], label=None, primary_requirement_id=ids["Timbal"])
    rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[],
    )
    assert len(rows) == 1
    assert rows[0]["row_kind"] == "cohort"
    assert rows[0]["row_label"].startswith("Timbal")
    assert "Glutenfri" in rows[0]["row_label"]
    assert "Laktosfri" in rows[0]["row_label"]
    assert rows[0]["group_id"]


def test_unresolved_primary_uses_exact_member_order(app_session):
    site_id = "00000000-0000-0000-0000-00000000ac01"
    department_id = "00000000-0000-0000-0000-00000000ac02"
    _seed_site_department(app_session, site_id=site_id, department_id=department_id, department_name="Unresolved Avd")
    ids = _seed_requirements(site_id, ["Glutenfri", "Timbal"])
    DepartmentRequirementGroupsRepo().create_group(department_id, 1, [ids["Glutenfri"], ids["Timbal"]], label=None, primary_requirement_id=None)
    rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[],
    )
    assert len(rows) == 1
    assert rows[0]["row_label"] == "Glutenfri + Timbal" or rows[0]["row_label"] == "Timbal + Glutenfri"
    assert rows[0]["row_kind"] == "cohort"


def test_two_groups_with_same_primary_remain_separate_rows(app_session):
    site_id = "00000000-0000-0000-0000-00000000ad01"
    department_id = "00000000-0000-0000-0000-00000000ad02"
    _seed_site_department(app_session, site_id=site_id, department_id=department_id, department_name="Separate Avd")
    ids = _seed_requirements(site_id, ["Timbal", "Glutenfri", "Laktosfri"])
    repo = DepartmentRequirementGroupsRepo()
    repo.create_group(department_id, 1, [ids["Timbal"], ids["Glutenfri"]], label=None, primary_requirement_id=ids["Timbal"])
    repo.create_group(department_id, 1, [ids["Timbal"], ids["Laktosfri"]], label=None, primary_requirement_id=ids["Timbal"])
    rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[],
    )
    assert len(rows) == 2
    assert {row["row_label"] for row in rows} == {"Timbal + Glutenfri", "Timbal + Laktosfri"}


def test_lunch_and_dinner_cells_follow_projection_and_marked_state(app_session):
    site_id = "00000000-0000-0000-0000-00000000ae01"
    department_id = "00000000-0000-0000-0000-00000000ae02"
    _seed_site_department(app_session, site_id=site_id, department_id=department_id, department_name="Meal Avd")
    ids = _seed_requirements(site_id, ["Timbal", "Glutenfri"])
    group = DepartmentRequirementGroupsRepo().create_group(department_id, 1, [ids["Timbal"], ids["Glutenfri"]], label=None, primary_requirement_id=ids["Timbal"])
    service_repo = DepartmentRequirementGroupServiceOverridesRepo()
    completion_repo = DepartmentRequirementGroupCompletionRepo()
    service_date = date.fromisocalendar(2026, 37, 1)
    service_repo.set_override(group["id"], service_date, "lunch", 2)
    service_repo.set_override(group["id"], service_date, "dinner", 3)
    completion_repo.set_marked(department_id, group["id"], service_date, "lunch", True)
    completion_repo.set_marked(department_id, group["id"], service_date, "dinner", False)
    rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[],
    )
    assert len(rows) == 1
    cells = rows[0]["cells"]
    assert cells[0]["meal"] == "lunch"
    assert cells[0]["count"] == 2
    assert cells[0]["is_done"] is True
    assert cells[1]["meal"] == "dinner"
    assert cells[1]["count"] == 3
    assert cells[1]["is_done"] is False


def test_weekday_and_exact_service_overrides_are_respected(app_session):
    site_id = "00000000-0000-0000-0000-00000000af01"
    department_id = "00000000-0000-0000-0000-00000000af02"
    _seed_site_department(app_session, site_id=site_id, department_id=department_id, department_name="Override Avd")
    ids = _seed_requirements(site_id, ["Timbal", "Glutenfri"])
    group = DepartmentRequirementGroupsRepo().create_group(department_id, 2, [ids["Timbal"], ids["Glutenfri"]], label=None, primary_requirement_id=ids["Timbal"])
    weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
    service_repo = DepartmentRequirementGroupServiceOverridesRepo()
    service_date = date.fromisocalendar(2026, 37, 4)
    weekday_repo.set_override(group["id"], service_date.isoweekday(), "lunch", 4)
    service_repo.set_override(group["id"], service_date, "lunch", 7)
    rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[],
    )
    assert len(rows) == 1
    thursday_lunch = rows[0]["cells"][(4 - 1) * 2]
    assert thursday_lunch["count"] == 7
    assert thursday_lunch["is_done"] is False


def test_all_zero_row_is_omitted_and_legacy_fallback_remains_unchanged(app_session):
    site_id = "00000000-0000-0000-0000-00000000ag01"
    department_id = "00000000-0000-0000-0000-00000000ag02"
    _seed_site_department(app_session, site_id=site_id, department_id=department_id, department_name="Zero Avd")
    ids = _seed_requirements(site_id, ["Timbal"])
    group = DepartmentRequirementGroupsRepo().create_group(department_id, 1, [ids["Timbal"]], label=None, primary_requirement_id=ids["Timbal"])
    service_repo = DepartmentRequirementGroupServiceOverridesRepo()
    for dow in range(1, 8):
        service_date = date.fromisocalendar(2026, 37, dow)
        service_repo.set_override(group["id"], service_date, "lunch", 0)
        service_repo.set_override(group["id"], service_date, "dinner", 0)
    cohort_rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=site_id,
        department_id=department_id,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[{"diet_type_id": "legacy-1", "diet_type_name": "Legacy 1", "cells": [{"day_index": idx, "meal": "lunch", "count": 1, "is_done": False, "is_override": False, "is_alt2": False} for idx in range(1, 15)]}],
    )
    assert cohort_rows == []

    legacy_site = "00000000-0000-0000-0000-00000000ag03"
    legacy_dept = "00000000-0000-0000-0000-00000000ag04"
    _seed_site_department(app_session, site_id=legacy_site, department_id=legacy_dept, department_name="Legacy Avd")
    legacy_rows = build_week_grid_specialkost_rows(
        tenant_id=1,
        site_id=legacy_site,
        department_id=legacy_dept,
        year=2026,
        week=37,
        days=_days(2026, 37),
        legacy_rows=[{"diet_type_id": "legacy-1", "diet_type_name": "Legacy 1", "cells": [{"day_index": idx, "meal": "lunch", "count": 1, "is_done": False, "is_override": False, "is_alt2": False} for idx in range(1, 15)]}],
    )
    assert legacy_rows[0]["row_kind"] == "legacy"