from __future__ import annotations

import inspect
import uuid

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.db import get_session
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.planera_v2 import day_context_resolver
from core.planera_v2.day_context_resolver import KommunDayContextResolverError, resolve_kommun_day_business_context

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


def _seed_requirement_group(site_id: str, department_id: str, *, label: str | None, requirement_names: list[str], quantity: int) -> str:
    requirement_ids: list[int] = []
    diet_repo = DietTypesRepo()
    for requirement_name in requirement_names:
        requirement_ids.append(
            diet_repo.create(site_id=site_id, name=requirement_name, default_select=False, semantics="atomic")
        )
    group = DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)
    return str(group["id"])


def _seed_weekview_counts(department_id: str, service_date: str, *, lunch: int, dinner: int) -> None:
    from datetime import date as _date

    year, week, weekday = _date.fromisoformat(service_date).isocalendar()
    db = get_session()
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS weekview_residents_count(
                    tenant_id TEXT,
                    department_id TEXT,
                    year INTEGER,
                    week INTEGER,
                    day_of_week INTEGER,
                    meal TEXT,
                    count INTEGER,
                    UNIQUE(tenant_id,department_id,year,week,day_of_week,meal)
                )
                """
            )
        )
        db.execute(
            text(
                """
                INSERT OR REPLACE INTO weekview_residents_count(
                    tenant_id, department_id, year, week, day_of_week, meal, count
                ) VALUES(:tenant_id,:department_id,:year,:week,:day_of_week,:meal,:count)
                """
            ),
            {
                "tenant_id": "1",
                "department_id": department_id,
                "year": year,
                "week": week,
                "day_of_week": weekday,
                "meal": "lunch",
                "count": lunch,
            },
        )
        db.execute(
            text(
                """
                INSERT OR REPLACE INTO weekview_residents_count(
                    tenant_id, department_id, year, week, day_of_week, meal, count
                ) VALUES(:tenant_id,:department_id,:year,:week,:day_of_week,:meal,:count)
                """
            ),
            {
                "tenant_id": "1",
                "department_id": department_id,
                "year": year,
                "week": week,
                "day_of_week": weekday,
                "meal": "dinner",
                "count": dinner,
            },
        )
        db.commit()
    finally:
        db.close()


def _seed_schedule_week(department_id: str, service_date: str, *, lunch: int | None = None, dinner: int | None = None) -> None:
    from datetime import date as _date

    _year, week, weekday = _date.fromisoformat(service_date).isocalendar()
    db = get_session()
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS department_residents_schedule(
                    department_id TEXT NOT NULL,
                    week INTEGER,
                    weekday INTEGER NOT NULL,
                    meal TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY(department_id, week, weekday, meal)
                )
                """
            )
        )
        if lunch is not None:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO department_residents_schedule(department_id, week, weekday, meal, count) VALUES(:d,:w,:day,'lunch',:c)"
                ),
                {"d": department_id, "w": week, "day": weekday, "c": lunch},
            )
        if dinner is not None:
            db.execute(
                text(
                    "INSERT OR REPLACE INTO department_residents_schedule(department_id, week, weekday, meal, count) VALUES(:d,:w,:day,'dinner',:c)"
                ),
                {"d": department_id, "w": week, "day": weekday, "c": dinner},
            )
        db.commit()
    finally:
        db.close()


def _seed_weekly_override(department_id: str, service_date: str, *, lunch: int | None = None, dinner: int | None = None) -> None:
    from datetime import date as _date

    year, week, _weekday = _date.fromisoformat(service_date).isocalendar()
    db = get_session()
    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS department_residents_weekly(
                    id TEXT PRIMARY KEY,
                    department_id TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    residents_lunch INTEGER NULL,
                    residents_dinner INTEGER NULL,
                    updated_at TEXT
                )
                """
            )
        )
        db.execute(
            text(
                """
                INSERT OR REPLACE INTO department_residents_weekly(id, department_id, year, week, residents_lunch, residents_dinner)
                VALUES(:id,:d,:y,:w,:lunch,:dinner)
                """
            ),
            {"id": str(uuid.uuid4()), "d": department_id, "y": year, "w": week, "lunch": lunch, "dinner": dinner},
        )
        db.commit()
    finally:
        db.close()


def test_resolver_rejects_wrong_tenant_site() -> None:
    site = _seed_site("Site A")
    _seed_department(site["id"], "Dept A", 10)

    with pytest.raises(KommunDayContextResolverError, match="site_not_owned"):
        resolve_kommun_day_business_context(
            tenant_id=2,
            site_id=site["id"],
            service_date="2026-09-03",
            meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
        )


def test_resolver_returns_all_site_departments_in_deterministic_order() -> None:
    site = _seed_site("Site B")
    alpha = _seed_department(site["id"], "Alpha", 7)
    zulu = _seed_department(site["id"], "Zulu", 9)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date="2026-09-03",
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    assert [dept.department_name for dept in context.departments] == ["Alpha", "Zulu"]
    assert list(context.lunch_baselines.keys()) == [alpha["id"], zulu["id"]]


def test_resolver_returns_exact_department_scope_when_requested() -> None:
    site = _seed_site("Site C")
    alpha = _seed_department(site["id"], "Alpha", 7)
    _seed_department(site["id"], "Zulu", 9)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date="2026-09-03",
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
        department_id=alpha["id"],
    )

    assert [dept.department_id for dept in context.departments] == [alpha["id"]]


def test_resolver_rejects_department_not_owned_by_site() -> None:
    site_a = _seed_site("Site D")
    site_b = _seed_site("Site E")
    _seed_department(site_b["id"], "Other", 5)

    with pytest.raises(KommunDayContextResolverError, match="department_scope_mismatch"):
        resolve_kommun_day_business_context(
            tenant_id=1,
            site_id=site_a["id"],
            service_date="2026-09-03",
            meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
            department_id=str(uuid.uuid4()),
        )


def test_resolver_omits_unlabeled_groups() -> None:
    site = _seed_site("Site L")
    dept = _seed_department(site["id"], "Dept", 10)
    unlabeled_group = _seed_requirement_group(site["id"], dept["id"], label="", requirement_names=["Positive"], quantity=1)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date="2026-09-03",
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    assert unlabeled_group not in context.requirement_projection_by_group_id
    assert context.requirement_projection_by_group_id == {}


def test_resolver_explicit_day_override_wins_over_lower_precedence() -> None:
    site = _seed_site("Site F")
    dept = _seed_department(site["id"], "Dept", 10)
    service_date = "2026-09-07"
    _seed_schedule_week(dept["id"], service_date, lunch=7, dinner=8)
    _seed_weekly_override(dept["id"], service_date, lunch=6, dinner=5)
    _seed_weekview_counts(dept["id"], service_date, lunch=11, dinner=9)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    assert context.lunch_baselines[dept["id"]] == 11
    assert context.dinner_baselines[dept["id"]] == 9


def test_resolver_schedule_week_precedence() -> None:
    site = _seed_site("Site G")
    dept = _seed_department(site["id"], "Dept", 10)
    service_date = "2026-09-07"
    _seed_schedule_week(dept["id"], service_date, lunch=7, dinner=8)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    assert context.lunch_baselines[dept["id"]] == 7
    assert context.dinner_baselines[dept["id"]] == 8


def test_resolver_weekly_override_fallback() -> None:
    site = _seed_site("Site H")
    dept = _seed_department(site["id"], "Dept", 10)
    service_date = "2026-09-07"
    _seed_weekly_override(dept["id"], service_date, lunch=6, dinner=5)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date=service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    assert context.lunch_baselines[dept["id"]] == 6
    assert context.dinner_baselines[dept["id"]] == 5


def test_resolver_supplied_meal_labels_preserved_and_missing_rejected() -> None:
    site = _seed_site("Site I")
    _seed_department(site["id"], "Dept", 10)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date="2026-09-03",
        meal_labels={"lunch": "Mitt mål", "dinner": "Kvällsmål"},
    )

    assert dict(context.meal_labels) == {"lunch": "Mitt mål", "dinner": "Kvällsmål"}

    with pytest.raises(KommunDayContextResolverError, match="missing_meal_label"):
        resolve_kommun_day_business_context(
            tenant_id=1,
            site_id=site["id"],
            service_date="2026-09-03",
            meal_labels={"lunch": "", "dinner": "Kvällsmål"},
        )


def test_resolver_labeled_requirement_groups_mapped_once_multi_key_remains_one_group() -> None:
    site = _seed_site("Site J")
    dept = _seed_department(site["id"], "Dept", 10)
    _seed_requirement_group(site["id"], dept["id"], label="One", requirement_names=["A"], quantity=1)
    _seed_requirement_group(site["id"], dept["id"], label="Two Keys", requirement_names=["B", "C"], quantity=1)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date="2026-09-03",
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    assert len(context.requirement_projection_by_group_id) == 2
    assert {meta.diet_name for meta in context.requirement_projection_by_group_id.values()} == {"One", "Two Keys"}


def test_resolver_blank_groups_omitted_regardless_of_effective_quantity() -> None:
    site = _seed_site("Site K")
    dept = _seed_department(site["id"], "Dept", 10)
    zero_group = _seed_requirement_group(site["id"], dept["id"], label="", requirement_names=["Zero"], quantity=0)
    positive_group = _seed_requirement_group(site["id"], dept["id"], label="", requirement_names=["Positive"], quantity=1)

    context = resolve_kommun_day_business_context(
        tenant_id=1,
        site_id=site["id"],
        service_date="2026-09-03",
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    assert zero_group not in context.requirement_projection_by_group_id
    assert positive_group not in context.requirement_projection_by_group_id


def test_resolver_has_no_alt_or_planera_service_dependency() -> None:
    source = inspect.getsource(day_context_resolver)
    assert "PlaneraService" not in source
    assert "alt1" not in source
    assert "alt2" not in source
    assert "alt_choice" not in source
    assert "dessert" not in source
