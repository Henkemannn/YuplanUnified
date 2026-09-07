from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.db import get_session
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.planera_v2 import kommun_day_application
from core.planera_v2.adapters.kommun_day_projection import KommunDayProjectionError
from core.planera_v2.day_context_resolver import KommunDayContextResolverError
from core.planera_v2.kommun_day_application import run_resolved_canonical_kommun_day
from core.planera_v2.day_context_resolver import resolve_kommun_day_business_context
from core.weekview.repo import WeekviewRepo

pytestmark = pytest.mark.usefixtures("app_session")


def _seed_site(name: str = "Site") -> dict:
    site, _ = SitesRepo().create_site(name, tenant_id=1)
    return site


def _seed_department(site_id: str, name: str, fixed: int) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=fixed,
    )
    return department


def _seed_weekview_counts(department_id: str, service_date: str, *, lunch: int, dinner: int) -> None:
    from datetime import date as _date

    year, week, weekday = _date.fromisoformat(service_date).isocalendar()
    WeekviewRepo().set_residents_counts(
        tenant_id=1,
        year=year,
        week=week,
        department_id=department_id,
        items=[
            {"day_of_week": weekday, "meal": "lunch", "count": lunch},
            {"day_of_week": weekday, "meal": "dinner", "count": dinner},
        ],
    )


def _seed_requirement_group(site_id: str, department_id: str, *, label: str | None, requirement_names: list[str], quantity: int) -> str:
    requirement_ids: list[int] = []
    diet_repo = DietTypesRepo()
    for requirement_name in requirement_names:
        requirement_ids.append(
            diet_repo.create(site_id=site_id, name=requirement_name, default_select=False, semantics="atomic")
        )
    group = DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)
    return str(group["id"])


def test_run_resolved_canonical_kommun_day_all_departments_real_data_end_to_end() -> None:
    site = _seed_site("E2E Site")
    alpha = _seed_department(site["id"], "Alpha", 10)
    beta = _seed_department(site["id"], "Beta", 8)
    service_date = "2026-09-07"
    _seed_weekview_counts(alpha["id"], service_date, lunch=12, dinner=9)
    _seed_weekview_counts(beta["id"], service_date, lunch=7, dinner=5)
    alpha_group = _seed_requirement_group(site["id"], alpha["id"], label="Glutenfri", requirement_names=["Glutenfri"], quantity=1)
    beta_group = _seed_requirement_group(site["id"], beta["id"], label="Laktosfri + Mjölkfri", requirement_names=["Laktosfri", "Mjölkfri"], quantity=1)
    expected_special_diets = sorted(
        [
            {"diet_type_id": f"group:{alpha_group}", "diet_name": "Glutenfri", "count": 1},
            {"diet_type_id": f"group:{beta_group}", "diet_name": "Laktosfri + Mjölkfri", "count": 1},
        ],
        key=lambda row: (row["diet_type_id"], row["diet_name"]),
    )

    payload = run_resolved_canonical_kommun_day(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
    )

    assert payload == run_resolved_canonical_kommun_day(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
    )
    assert payload["site_id"] == site["id"]
    assert payload["site_name"] == "E2E Site"
    assert payload["date"] == service_date
    assert payload["meal_labels"] == {"lunch": "Lunch", "dinner": "Kvällsmat"}
    assert [department["department_id"] for department in payload["departments"]] == [alpha["id"], beta["id"]]
    assert payload["departments"][0]["meals"]["lunch"] == {
        "residents_total": 12,
        "special_diets": [{"diet_type_id": f"group:{alpha_group}", "diet_name": "Glutenfri", "count": 1}],
        "normal_diet_count": 11,
    }
    assert payload["departments"][1]["meals"]["dinner"] == {
        "residents_total": 5,
        "special_diets": [
            {"diet_type_id": f"group:{beta_group}", "diet_name": "Laktosfri + Mjölkfri", "count": 1},
        ],
        "normal_diet_count": 4,
    }
    assert payload["totals"]["lunch"] == {
        "residents_total": 19,
        "special_diets": expected_special_diets,
        "normal_diet_count": 17,
    }
    assert payload["totals"]["dinner"] == {
        "residents_total": 14,
        "special_diets": expected_special_diets,
        "normal_diet_count": 12,
    }


def test_run_resolved_canonical_kommun_day_one_department_scope_and_tenant_guard() -> None:
    site = _seed_site("Scoped E2E Site")
    alpha = _seed_department(site["id"], "Alpha", 10)
    _seed_department(site["id"], "Beta", 8)
    service_date = "2026-09-07"
    _seed_weekview_counts(alpha["id"], service_date, lunch=11, dinner=9)
    _seed_requirement_group(site["id"], alpha["id"], label="Glutenfri", requirement_names=["Glutenfri"], quantity=1)

    scoped_payload = run_resolved_canonical_kommun_day(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        department_id=alpha["id"],
    )

    assert [department["department_id"] for department in scoped_payload["departments"]] == [alpha["id"]]
    assert scoped_payload["departments"][0]["meals"]["lunch"]["residents_total"] == 11
    assert scoped_payload["departments"][0]["meals"]["dinner"]["residents_total"] == 9

    with pytest.raises(KommunDayContextResolverError, match="site_not_owned"):
        run_resolved_canonical_kommun_day(
            tenant_id=2,
            site_id=site["id"],
            service_date=service_date,
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        )


def test_run_resolved_canonical_kommun_day_unlabeled_positive_group_fails_closed() -> None:
    site = _seed_site("Fail Closed E2E Site")
    department = _seed_department(site["id"], "Alpha", 10)
    service_date = "2026-09-07"
    _seed_weekview_counts(department["id"], service_date, lunch=10, dinner=8)
    _seed_requirement_group(site["id"], department["id"], label="", requirement_names=["Positive"], quantity=1)

    with pytest.raises(KommunDayProjectionError, match="missing_group_projection"):
        run_resolved_canonical_kommun_day(
            tenant_id=1,
            site_id=site["id"],
            service_date=service_date,
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        )


def test_run_resolved_canonical_kommun_day_is_deterministic_and_has_no_legacy_dependencies() -> None:
    source = inspect.getsource(kommun_day_application)
    assert "PlaneraService" not in source
    assert "alt1" not in source
    assert "alt2" not in source
    assert "alt_choice" not in source
    assert "dessert" not in source

    site = _seed_site("Deterministic E2E Site")
    department = _seed_department(site["id"], "Alpha", 10)
    service_date = "2026-09-07"
    _seed_weekview_counts(department["id"], service_date, lunch=10, dinner=8)
    _seed_requirement_group(site["id"], department["id"], label="Glutenfri", requirement_names=["Glutenfri"], quantity=1)

    first = run_resolved_canonical_kommun_day(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
    )
    second = run_resolved_canonical_kommun_day(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
    )

    assert first == second