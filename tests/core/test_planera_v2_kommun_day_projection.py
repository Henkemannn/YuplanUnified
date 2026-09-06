from __future__ import annotations

from copy import deepcopy

import pytest

from core.planera_v2.adapters.kommun_day_projection import (
    KommunDayProjectionError,
    KommunDepartmentProjectionContext,
    RequirementGroupProjection,
    project_canonical_kommun_day,
)
from core.planera_v2.domain import Deviation, PlanRequest, PlanResult, Totals, UnitBreakdown, UnitInput
from core.planera_v2.shadow import ProductionShadowRun
from core.planera_v2.acceptance import ProductionAcceptanceResult


def _meal_run(
    *,
    meal_key: str,
    departments: list[tuple[str, str, int, int]],
    group_refs: list[dict[str, object]],
    per_unit_rows: dict[str, dict[str, dict[str, object]]],
    totals: tuple[int, int, int],
    accepted: bool = True,
    diagnostic_result: PlanResult | None = None,
    site_id: str = "site-1",
    service_date: str = "2026-04-14",
) -> ProductionShadowRun:
    units = [UnitInput(unit_id=unit_id, baseline_total=baseline) for unit_id, _name, baseline, _dev in departments]
    deviations: list[Deviation] = []
    for unit_id, _name, _baseline, deviation_total in departments:
        if deviation_total:
            deviations.append(Deviation(form="unspecified", category_keys=[f"req_{unit_id}"], quantity=deviation_total, unit_id=unit_id))
    request = PlanRequest(
        baseline=sum(baseline for _unit_id, _name, baseline, _dev in departments),
        units=units,
        deviations=deviations,
        context={
            "site_id": site_id,
            "date": service_date,
            "meal_key": meal_key,
            "requirement_group_refs": group_refs,
        },
    )
    if diagnostic_result is None:
        per_unit_breakdown = {
            unit_id: UnitBreakdown(
                baseline_total=baseline,
                deviation_total=deviation_total,
                normal_total=max(0, baseline - deviation_total),
            )
            for unit_id, _name, baseline, deviation_total in departments
        }
        diagnostic_result = PlanResult(
            totals=Totals(*totals),
            per_unit={unit_id: deviation_total for unit_id, _name, _baseline, deviation_total in departments},
            per_unit_breakdown=per_unit_breakdown,
        )
    return ProductionShadowRun(
        request=request,
        acceptance=ProductionAcceptanceResult(accepted=accepted),
        diagnostic_result=diagnostic_result,
    )


def _accepted_day() -> tuple[list[KommunDepartmentProjectionContext], dict[str, ProductionShadowRun], dict[str, RequirementGroupProjection]]:
    departments = [
        KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A"),
        KommunDepartmentProjectionContext(department_id="unit-b", department_name="Unit B"),
    ]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2), ("unit-b", "Unit B", 8, 0)],
        group_refs=[
            {"group_id": "group-a", "unit_id": "unit-a", "quantity": 2},
        ],
        per_unit_rows={
            "unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}},
            "unit-b": {"totals": {"deviation_total": 0, "normal_total": 8}},
        },
        totals=(18, 2, 16),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 7, 1), ("unit-b", "Unit B", 5, 1)],
        group_refs=[
            {"group_id": "group-b", "unit_id": "unit-a", "quantity": 1},
            {"group_id": "group-c", "unit_id": "unit-b", "quantity": 1},
        ],
        per_unit_rows={
            "unit-a": {"totals": {"deviation_total": 1, "normal_total": 6}},
            "unit-b": {"totals": {"deviation_total": 1, "normal_total": 4}},
        },
        totals=(12, 2, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-b", diet_name="Compat B"),
        "group-c": RequirementGroupProjection(group_id="group-c", diet_type_id="compat-c", diet_name="Compat C"),
    }
    return departments, {"lunch": lunch, "dinner": dinner}, projections


def _single_department_day(*, lunch_deviation: int = 1, dinner_deviation: int = 1) -> tuple[list[KommunDepartmentProjectionContext], dict[str, ProductionShadowRun], dict[str, RequirementGroupProjection]]:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, lunch_deviation)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": lunch_deviation}] if lunch_deviation else [],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": lunch_deviation, "normal_total": max(0, 10 - lunch_deviation)}}},
        totals=(10, lunch_deviation, max(0, 10 - lunch_deviation)),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, dinner_deviation)],
        group_refs=[{"group_id": "group-b", "unit_id": "unit-a", "quantity": dinner_deviation}] if dinner_deviation else [],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": dinner_deviation, "normal_total": max(0, 10 - dinner_deviation)}}},
        totals=(10, dinner_deviation, max(0, 10 - dinner_deviation)),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-b", diet_name="Compat B"),
    }
    return departments, {"lunch": lunch, "dinner": dinner}, projections


def _single_department_zero_day() -> tuple[list[KommunDepartmentProjectionContext], dict[str, ProductionShadowRun], dict[str, RequirementGroupProjection]]:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 0, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 0}}},
        totals=(0, 0, 0),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 0, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 0}}},
        totals=(0, 0, 0),
    )
    return departments, {"lunch": lunch, "dinner": dinner}, {}


def test_projection_returns_exact_day_shape_and_preserves_department_order() -> None:
    departments, meal_runs, projections = _accepted_day()
    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert set(payload.keys()) == {"site_id", "site_name", "date", "meal_labels", "departments", "totals"}
    assert [row["department_id"] for row in payload["departments"]] == ["unit-a", "unit-b"]
    assert payload["departments"][0]["meals"]["lunch"]["residents_total"] == 10
    assert payload["departments"][1]["meals"]["dinner"]["residents_total"] == 5
    assert payload["totals"]["lunch"]["normal_diet_count"] == 16
    assert payload["totals"]["dinner"]["normal_diet_count"] == 10


def test_projection_has_exact_top_level_keys() -> None:
    departments, meal_runs, projections = _accepted_day()
    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert set(payload.keys()) == {"site_id", "site_name", "date", "meal_labels", "departments", "totals"}


def test_projection_has_exact_meal_block_keys() -> None:
    departments, meal_runs, projections = _accepted_day()
    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    lunch = payload["departments"][0]["meals"]["lunch"]
    assert set(lunch.keys()) == {"residents_total", "special_diets", "normal_diet_count"}


def test_projection_missing_lunch_label_raises_missing_meal_label() -> None:
    departments, meal_runs, projections = _accepted_day()
    with pytest.raises(KommunDayProjectionError, match="missing_meal_label"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"dinner": "Kvällsmat"},
            departments=departments,
            meal_runs=meal_runs,
            requirement_projection_by_group_id=projections,
        )


def test_projection_missing_dinner_label_raises_missing_meal_label() -> None:
    departments, meal_runs, projections = _accepted_day()
    with pytest.raises(KommunDayProjectionError, match="missing_meal_label"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch"},
            departments=departments,
            meal_runs=meal_runs,
            requirement_projection_by_group_id=projections,
        )


def test_projection_normal_only_single_department_with_lunch_and_dinner() -> None:
    departments, meal_runs, projections = _single_department_day(lunch_deviation=0, dinner_deviation=0)
    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert payload["departments"][0]["meals"]["lunch"] == {"residents_total": 10, "special_diets": [], "normal_diet_count": 10}
    assert payload["departments"][0]["meals"]["dinner"] == {"residents_total": 10, "special_diets": [], "normal_diet_count": 10}


def test_projection_multiple_departments_preserve_supplied_order() -> None:
    departments, meal_runs, projections = _accepted_day()
    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert [row["department_id"] for row in payload["departments"]] == ["unit-a", "unit-b"]


def test_projection_lunch_and_dinner_may_have_different_baselines() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 12, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 11}}},
        totals=(12, 1, 11),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 8, 1)],
        group_refs=[{"group_id": "group-b", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 7}}},
        totals=(8, 1, 7),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-b", diet_name="Compat B"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    assert payload["departments"][0]["meals"]["lunch"]["residents_total"] == 12
    assert payload["departments"][0]["meals"]["dinner"]["residents_total"] == 8


def test_projection_lunch_and_dinner_may_have_different_deviation_quantities() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[{"group_id": "group-b", "unit_id": "unit-a", "quantity": 2}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
    )
    projections = {
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-b", diet_name="Compat B"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    assert payload["departments"][0]["meals"]["lunch"]["special_diets"] == []
    assert payload["departments"][0]["meals"]["dinner"]["special_diets"] == [{"diet_type_id": "compat-b", "diet_name": "Compat B", "count": 2}]


def test_projection_wrong_site_raises_unit_set_mismatch() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 9),
        site_id="other-site",
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
    }

    with pytest.raises(KommunDayProjectionError, match="unit_set_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_wrong_date_raises_unit_set_mismatch() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 9),
        service_date="2026-04-15",
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
    }

    with pytest.raises(KommunDayProjectionError, match="unit_set_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_zero_resident_accepted_department_projects_zero_shape() -> None:
    departments, meal_runs, projections = _single_department_zero_day()
    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert payload["departments"][0]["meals"]["lunch"] == {"residents_total": 0, "special_diets": [], "normal_diet_count": 0}
    assert payload["departments"][0]["meals"]["dinner"] == {"residents_total": 0, "special_diets": [], "normal_diet_count": 0}


def test_projection_no_deviations_projects_empty_special_diets() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id={},
    )

    assert payload["totals"]["lunch"]["special_diets"] == []
    assert payload["totals"]["dinner"]["special_diets"] == []


def test_projection_atomic_group_projects_once_and_not_split_into_category_rows() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-atomic", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 9),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-atomic": RequirementGroupProjection(group_id="group-atomic", diet_type_id="compat-atomic", diet_name="Atomic Label"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    assert payload["departments"][0]["meals"]["lunch"]["special_diets"] == [{"diet_type_id": "compat-atomic", "diet_name": "Atomic Label", "count": 1}]


def test_projection_multi_key_group_quantity_one_projects_one_row_and_not_separate_keys() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-ab", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 9),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-ab": RequirementGroupProjection(group_id="group-ab", diet_type_id="compat-gluten-lactose", diet_name="Gluten + lactose"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    lunch_rows = payload["departments"][0]["meals"]["lunch"]["special_diets"]
    assert lunch_rows == [{"diet_type_id": "compat-gluten-lactose", "diet_name": "Gluten + lactose", "count": 1}]
    assert all(row["diet_type_id"] != "gluten_free" for row in lunch_rows)
    assert all(row["diet_type_id"] != "lactose_free" for row in lunch_rows)


def test_projection_two_groups_same_compatibility_id_aggregate_when_names_match() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[
            {"group_id": "group-a", "unit_id": "unit-a", "quantity": 1},
            {"group_id": "group-b", "unit_id": "unit-a", "quantity": 1},
        ],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-shared", diet_name="Shared Label"),
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-shared", diet_name="Shared Label"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    assert payload["departments"][0]["meals"]["lunch"]["special_diets"] == [{"diet_type_id": "compat-shared", "diet_name": "Shared Label", "count": 2}]
    assert payload["totals"]["lunch"]["special_diets"] == [{"diet_type_id": "compat-shared", "diet_name": "Shared Label", "count": 2}]


def test_projection_total_special_diets_aggregate_across_multiple_departments() -> None:
    departments = [
        KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A"),
        KommunDepartmentProjectionContext(department_id="unit-b", department_name="Unit B"),
    ]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1), ("unit-b", "Unit B", 8, 1)],
        group_refs=[
            {"group_id": "group-a", "unit_id": "unit-a", "quantity": 1},
            {"group_id": "group-b", "unit_id": "unit-b", "quantity": 1},
        ],
        per_unit_rows={
            "unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}},
            "unit-b": {"totals": {"deviation_total": 1, "normal_total": 7}},
        },
        totals=(18, 2, 16),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0), ("unit-b", "Unit B", 8, 0)],
        group_refs=[],
        per_unit_rows={
            "unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}},
            "unit-b": {"totals": {"deviation_total": 0, "normal_total": 8}},
        },
        totals=(18, 0, 18),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-b", diet_name="Compat B"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    assert payload["totals"]["lunch"]["special_diets"] == [
        {"diet_type_id": "compat-a", "diet_name": "Compat A", "count": 1},
        {"diet_type_id": "compat-b", "diet_name": "Compat B", "count": 1},
    ]


def test_projection_baseline_aggregate_mismatch_raises_projection_quantity_mismatch() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(11, 1, 9),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
    }

    with pytest.raises(KommunDayProjectionError, match="projection_quantity_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_normal_aggregate_mismatch_raises_projection_quantity_mismatch() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 10),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
    }

    with pytest.raises(KommunDayProjectionError, match="projection_quantity_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_missing_lunch_raises_missing_meal_run() -> None:
    departments, meal_runs, projections = _accepted_day()
    with pytest.raises(KommunDayProjectionError, match="missing_meal_run"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"dinner": meal_runs["dinner"]},
            requirement_projection_by_group_id=projections,
        )


def test_projection_missing_dinner_raises_missing_meal_run() -> None:
    departments, meal_runs, projections = _accepted_day()
    with pytest.raises(KommunDayProjectionError, match="missing_meal_run"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": meal_runs["lunch"]},
            requirement_projection_by_group_id=projections,
        )


def test_projection_accepted_lunch_with_missing_diagnostic_result_raises() -> None:
    departments, meal_runs, projections = _accepted_day()
    lunch = ProductionShadowRun(
        request=meal_runs["lunch"].request,
        acceptance=meal_runs["lunch"].acceptance,
        diagnostic_result=None,
    )
    with pytest.raises(KommunDayProjectionError, match="missing_diagnostic_result"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": meal_runs["dinner"]},
            requirement_projection_by_group_id=projections,
        )


def test_projection_accepted_dinner_with_missing_diagnostic_result_raises() -> None:
    departments, meal_runs, projections = _accepted_day()
    dinner = ProductionShadowRun(
        request=meal_runs["dinner"].request,
        acceptance=meal_runs["dinner"].acceptance,
        diagnostic_result=None,
    )
    with pytest.raises(KommunDayProjectionError, match="missing_diagnostic_result"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": meal_runs["lunch"], "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_missing_department_in_request_raises_unit_set_mismatch() -> None:
    departments, meal_runs, projections = _accepted_day()
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 2}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
    )
    with pytest.raises(KommunDayProjectionError, match="unit_set_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": meal_runs["dinner"]},
            requirement_projection_by_group_id=projections,
        )


def test_projection_unexpected_department_in_request_raises_unit_set_mismatch() -> None:
    departments, meal_runs, projections = _accepted_day()
    extra_lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2), ("unit-x", "Unit X", 4, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 2}, {"group_id": "group-x", "unit_id": "unit-x", "quantity": 1}],
        per_unit_rows={
            "unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}},
            "unit-x": {"totals": {"deviation_total": 1, "normal_total": 3}},
        },
        totals=(14, 3, 11),
    )
    with pytest.raises(KommunDayProjectionError, match="unit_set_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": extra_lunch, "dinner": meal_runs["dinner"]},
            requirement_projection_by_group_id=projections,
        )


def test_projection_positive_group_without_projection_mapping_raises_missing_group_projection() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 9),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    with pytest.raises(KommunDayProjectionError, match="missing_group_projection"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id={},
        )


def test_projection_unit_quantity_mismatch_raises_projection_quantity_mismatch() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
    }
    with pytest.raises(KommunDayProjectionError, match="projection_quantity_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_meal_total_mismatch_raises_projection_quantity_mismatch() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 99, 9),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Compat A"),
    }
    with pytest.raises(KommunDayProjectionError, match="projection_quantity_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_same_compatibility_id_with_conflicting_names_raises_projection_label_conflict() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[
            {"group_id": "group-a", "unit_id": "unit-a", "quantity": 1},
            {"group_id": "group-b", "unit_id": "unit-a", "quantity": 1},
        ],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Name A"),
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-a", diet_name="Name B"),
    }
    with pytest.raises(KommunDayProjectionError, match="projection_label_conflict"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id=projections,
        )


def test_projection_does_not_mutate_inputs() -> None:
    departments, meal_runs, projections = _accepted_day()
    departments_copy = deepcopy(departments)
    runs_copy = deepcopy(meal_runs)
    projections_copy = deepcopy(projections)
    meal_labels = {"lunch": "Lunch", "dinner": "Kvällsmat"}
    meal_labels_copy = deepcopy(meal_labels)

    project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels=meal_labels,
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert departments == departments_copy
    assert meal_runs == runs_copy
    assert projections == projections_copy
    assert meal_labels == meal_labels_copy


def test_projection_deterministic_special_diets_ordering() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[
            {"group_id": "group-b", "unit_id": "unit-a", "quantity": 1},
            {"group_id": "group-a", "unit_id": "unit-a", "quantity": 1},
        ],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Label A"),
        "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-b", diet_name="Label B"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    assert payload["departments"][0]["meals"]["lunch"]["special_diets"] == [
        {"diet_type_id": "compat-a", "diet_name": "Label A", "count": 1},
        {"diet_type_id": "compat-b", "diet_name": "Label B", "count": 1},
    ]


def test_projection_repeated_projection_returns_equal_output() -> None:
    departments, meal_runs, projections = _accepted_day()
    payload_a = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )
    payload_b = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert payload_a == payload_b


def test_projection_explicitly_does_not_introduce_alt1_or_alt2_fields() -> None:
    departments, meal_runs, projections = _accepted_day()
    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert "alt1" not in payload
    assert "alt2" not in payload
    for department in payload["departments"]:
        for meal in department["meals"].values():
            assert "alt1" not in meal
            assert "alt2" not in meal


def test_projection_is_pure_and_does_not_mutate_inputs() -> None:
    departments, meal_runs, projections = _accepted_day()
    departments_copy = deepcopy(departments)
    runs_copy = deepcopy(meal_runs)
    projections_copy = deepcopy(projections)

    project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs=meal_runs,
        requirement_projection_by_group_id=projections,
    )

    assert departments == departments_copy
    assert meal_runs.keys() == runs_copy.keys()
    assert projections == projections_copy


def test_projection_requires_accepted_meal_runs_and_diagnostic_results() -> None:
    departments, meal_runs, projections = _accepted_day()
    blocked = dict(meal_runs)
    blocked["lunch"] = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 2}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
        accepted=False,
    )
    with pytest.raises(KommunDayProjectionError, match="blocked_meal_run"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs=blocked,
            requirement_projection_by_group_id=projections,
        )

    missing_diag = dict(meal_runs)
    missing_diag["lunch"] = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 2)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 2}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
        totals=(10, 2, 8),
        diagnostic_result=None,
    )
    missing_diag["lunch"] = ProductionShadowRun(
        request=missing_diag["lunch"].request,
        acceptance=missing_diag["lunch"].acceptance,
        diagnostic_result=None,
    )
    with pytest.raises(KommunDayProjectionError, match="missing_diagnostic_result"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs=missing_diag,
            requirement_projection_by_group_id=projections,
        )


def test_projection_requires_both_meals_and_matching_unit_sets() -> None:
    departments, meal_runs, projections = _accepted_day()
    with pytest.raises(KommunDayProjectionError, match="missing_meal_run"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": meal_runs["lunch"]},
            requirement_projection_by_group_id=projections,
        )

    bad_departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    with pytest.raises(KommunDayProjectionError, match="unit_set_mismatch"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=bad_departments,
            meal_runs=meal_runs,
            requirement_projection_by_group_id=projections,
        )


def test_projection_projects_multi_key_group_once_and_aggregates_same_compatibility_id() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[
            {"group_id": "group-ab", "unit_id": "unit-a", "quantity": 1},
        ],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 9),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )
    projections = {
        "group-ab": RequirementGroupProjection(group_id="group-ab", diet_type_id="compat-gluten-lactose", diet_name="Gluten + lactose"),
    }

    payload = project_canonical_kommun_day(
        site_id="site-1",
        site_name="Site One",
        service_date="2026-04-14",
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        departments=departments,
        meal_runs={"lunch": lunch, "dinner": dinner},
        requirement_projection_by_group_id=projections,
    )

    lunch_rows = payload["departments"][0]["meals"]["lunch"]["special_diets"]
    assert lunch_rows == [{"diet_type_id": "compat-gluten-lactose", "diet_name": "Gluten + lactose", "count": 1}]
    assert payload["totals"]["lunch"]["special_diets"] == [{"diet_type_id": "compat-gluten-lactose", "diet_name": "Gluten + lactose", "count": 1}]


def test_projection_rejects_label_conflicts_and_missing_projection_metadata() -> None:
    departments = [KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A")]
    lunch = _meal_run(
        meal_key="lunch",
        departments=[("unit-a", "Unit A", 10, 1)],
        group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 1, "normal_total": 9}}},
        totals=(10, 1, 9),
    )
    dinner = _meal_run(
        meal_key="dinner",
        departments=[("unit-a", "Unit A", 10, 0)],
        group_refs=[],
        per_unit_rows={"unit-a": {"totals": {"deviation_total": 0, "normal_total": 10}}},
        totals=(10, 0, 10),
    )

    with pytest.raises(KommunDayProjectionError, match="missing_group_projection"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={"lunch": lunch, "dinner": dinner},
            requirement_projection_by_group_id={},
        )

    with pytest.raises(KommunDayProjectionError, match="projection_label_conflict"):
        project_canonical_kommun_day(
            site_id="site-1",
            site_name="Site One",
            service_date="2026-04-14",
            meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
            departments=departments,
            meal_runs={
                "lunch": _meal_run(
                    meal_key="lunch",
                    departments=[("unit-a", "Unit A", 10, 2)],
                    group_refs=[
                        {"group_id": "group-a", "unit_id": "unit-a", "quantity": 1},
                        {"group_id": "group-b", "unit_id": "unit-a", "quantity": 1},
                    ],
                    per_unit_rows={"unit-a": {"totals": {"deviation_total": 2, "normal_total": 8}}},
                    totals=(10, 2, 8),
                ),
                "dinner": dinner,
            },
            requirement_projection_by_group_id={
                "group-a": RequirementGroupProjection(group_id="group-a", diet_type_id="compat-a", diet_name="Label A"),
                "group-b": RequirementGroupProjection(group_id="group-b", diet_type_id="compat-a", diet_name="Label B"),
            },
        )


def test_projection_does_not_use_inputs_that_look_like_legacy_or_engine_calls() -> None:
    from core.planera_v2.adapters import kommun_day_projection as module
    import inspect

    source = inspect.getsource(module)
    assert "get_session" not in source
    assert "compute_plan(" not in source
    assert "validate_plan_request_for_production(" not in source
