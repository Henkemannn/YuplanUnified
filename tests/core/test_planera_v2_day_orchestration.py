from __future__ import annotations

from copy import deepcopy

import pytest

from core.planera_v2 import day_orchestration
from core.planera_v2.acceptance import ProductionAcceptanceResult
from core.planera_v2.adapters.kommun_day_projection import (
    KommunDayProjectionError,
    KommunDepartmentProjectionContext,
    RequirementGroupProjection,
    project_canonical_kommun_day,
)
from core.planera_v2.day_orchestration import (
    KommunDayBusinessContext,
    KommunDayOrchestrationError,
    KommunGroupCompatibilityMetadata,
    run_canonical_kommun_day,
)
from core.planera_v2.domain import PlanRequest, PlanResult, Totals, UnitBreakdown, UnitInput
from core.planera_v2.shadow import ProductionShadowRun


def _meal_run(
    *,
    meal_key: str,
    baselines: dict[str, int],
    deviations: dict[str, int],
    accepted: bool = True,
    requirement_group_refs: list[dict[str, object]] | None = None,
    site_id: str = "site-a",
    service_date: str = "2026-09-03",
) -> ProductionShadowRun:
    units = [UnitInput(unit_id=unit_id, baseline_total=baseline) for unit_id, baseline in baselines.items()]
    per_unit_breakdown = {
        unit_id: UnitBreakdown(
            baseline_total=baseline,
            deviation_total=deviations.get(unit_id, 0),
            normal_total=max(0, baseline - deviations.get(unit_id, 0)),
        )
        for unit_id, baseline in baselines.items()
    }
    total_baseline = sum(baselines.values())
    total_deviation = sum(deviations.values())
    result = PlanResult(
        totals=Totals(total_baseline, total_deviation, max(0, total_baseline - total_deviation)),
        per_unit={unit_id: deviations.get(unit_id, 0) for unit_id in baselines},
        per_unit_breakdown=per_unit_breakdown,
    )
    request = PlanRequest(
        baseline=total_baseline,
        units=units,
        deviations=[
            __import__("core.planera_v2.domain", fromlist=["Deviation"]).Deviation(
                form="unspecified",
                category_keys=[f"group:{unit_id}"],
                quantity=deviations.get(unit_id, 0),
                unit_id=unit_id,
            )
            for unit_id in baselines
            if deviations.get(unit_id, 0)
        ],
        context={
            "site_id": site_id,
            "date": service_date,
            "meal_key": meal_key,
            "requirement_group_refs": requirement_group_refs or [],
        },
    )
    return ProductionShadowRun(request=request, acceptance=ProductionAcceptanceResult(accepted=accepted), diagnostic_result=result)


def _business_context() -> KommunDayBusinessContext:
    departments = (
        KommunDepartmentProjectionContext(department_id="unit-b", department_name="Unit B"),
        KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A"),
    )
    return KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-a",
        site_name="Site A",
        service_date="2026-09-03",
        departments=departments,
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        lunch_baselines={"unit-b": 8, "unit-a": 10},
        dinner_baselines={"unit-b": 5, "unit-a": 7},
        requirement_projection_by_group_id={
            "group-a": KommunGroupCompatibilityMetadata(group_id="group-a", diet_name="Compat A"),
            "group-b": KommunGroupCompatibilityMetadata(group_id="group-b", diet_name="Compat B"),
            "group-c": KommunGroupCompatibilityMetadata(group_id="group-c", diet_name="Compat C"),
        },
    )


def test_run_canonical_kommun_day_calls_shadow_once_per_meal_and_projects(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _business_context()
    shadow_calls: list[dict[str, object]] = []
    projection_calls: list[dict[str, object]] = []

    def _fake_shadow(*, site_id: str, service_date: str, meal_key: str, unit_baselines: dict[str, object], expected_unit_ids):
        shadow_calls.append(
            {
                "site_id": site_id,
                "service_date": service_date,
                "meal_key": meal_key,
                "unit_baselines": dict(unit_baselines),
                "expected_unit_ids": tuple(expected_unit_ids),
            }
        )
        if meal_key == "lunch":
            return _meal_run(
                meal_key=meal_key,
                baselines={"unit-b": 8, "unit-a": 10},
                deviations={"unit-b": 0, "unit-a": 2},
                requirement_group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 2}],
            )
        return _meal_run(
            meal_key=meal_key,
            baselines={"unit-b": 5, "unit-a": 7},
            deviations={"unit-b": 1, "unit-a": 1},
            requirement_group_refs=[
                {"group_id": "group-b", "unit_id": "unit-a", "quantity": 1},
                {"group_id": "group-c", "unit_id": "unit-b", "quantity": 1},
            ],
        )

    def _fake_project(*, site_id: str, site_name: str, service_date: str, meal_labels, departments, meal_runs, requirement_projection_by_group_id):
        projection_calls.append(
            {
                "site_id": site_id,
                "site_name": site_name,
                "service_date": service_date,
                "meal_labels": dict(meal_labels),
                "departments": tuple((dept.department_id, dept.department_name) for dept in departments),
                "meal_keys": tuple(sorted(meal_runs.keys())),
                "requirement_projection_by_group_id": {
                    group_id: (projection.group_id, projection.diet_type_id, projection.diet_name)
                    for group_id, projection in requirement_projection_by_group_id.items()
                },
            }
        )
        return {
            "site_id": site_id,
            "site_name": site_name,
            "date": service_date,
            "meal_labels": dict(meal_labels),
            "departments": [
                {"department_id": dept.department_id, "department_name": dept.department_name, "meals": {}}
                for dept in departments
            ],
            "totals": {"lunch": {}, "dinner": {}},
        }

    monkeypatch.setattr(day_orchestration, "run_canonical_requirement_groups_in_production_shadow", _fake_shadow)
    monkeypatch.setattr(day_orchestration, "project_canonical_kommun_day", _fake_project)

    payload = run_canonical_kommun_day(context)

    assert len(shadow_calls) == 2
    assert [call["meal_key"] for call in shadow_calls] == ["lunch", "dinner"]
    assert shadow_calls[0]["unit_baselines"] == {"unit-b": 8, "unit-a": 10}
    assert shadow_calls[1]["unit_baselines"] == {"unit-b": 5, "unit-a": 7}
    assert shadow_calls[0]["expected_unit_ids"] == ("unit-b", "unit-a")
    assert shadow_calls[1]["expected_unit_ids"] == ("unit-b", "unit-a")
    assert len(projection_calls) == 1
    assert projection_calls[0]["requirement_projection_by_group_id"] == {
        "group-a": ("group-a", "group:group-a", "Compat A"),
        "group-b": ("group-b", "group:group-b", "Compat B"),
        "group-c": ("group-c", "group:group-c", "Compat C"),
    }
    assert payload["site_name"] == "Site A"


def test_run_canonical_kommun_day_preserves_input_immutability(monkeypatch: pytest.MonkeyPatch) -> None:
    meal_labels = {"lunch": "Lunch", "dinner": "Kvällsmat"}
    lunch_baselines = {"unit-b": 8, "unit-a": 10}
    dinner_baselines = {"unit-b": 5, "unit-a": 7}
    requirement_projection_by_group_id = {
        "group-a": KommunGroupCompatibilityMetadata(group_id="group-a", diet_name="Compat A"),
        "group-b": KommunGroupCompatibilityMetadata(group_id="group-b", diet_name="Compat B"),
        "group-c": KommunGroupCompatibilityMetadata(group_id="group-c", diet_name="Compat C"),
    }
    departments = (
        KommunDepartmentProjectionContext(department_id="unit-b", department_name="Unit B"),
        KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A"),
    )
    context = KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-a",
        site_name="Site A",
        service_date="2026-09-03",
        departments=departments,
        meal_labels=meal_labels,
        lunch_baselines=lunch_baselines,
        dinner_baselines=dinner_baselines,
        requirement_projection_by_group_id=requirement_projection_by_group_id,
    )
    snapshot = {
        "meal_labels": deepcopy(meal_labels),
        "lunch_baselines": deepcopy(lunch_baselines),
        "dinner_baselines": deepcopy(dinner_baselines),
        "requirement_projection_by_group_id": deepcopy(requirement_projection_by_group_id),
        "departments": deepcopy(departments),
    }

    monkeypatch.setattr(
        day_orchestration,
        "run_canonical_requirement_groups_in_production_shadow",
        lambda **kwargs: _meal_run(
            meal_key=str(kwargs["meal_key"]),
            baselines=dict(kwargs["unit_baselines"]),
            deviations={"unit-a": 1},
            requirement_group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        ),
    )
    monkeypatch.setattr(
        day_orchestration,
        "project_canonical_kommun_day",
        lambda **kwargs: {"departments": [], "totals": {"lunch": {}, "dinner": {}}},
    )

    run_canonical_kommun_day(context)

    assert meal_labels == snapshot["meal_labels"]
    assert lunch_baselines == snapshot["lunch_baselines"]
    assert dinner_baselines == snapshot["dinner_baselines"]
    assert requirement_projection_by_group_id == snapshot["requirement_projection_by_group_id"]
    assert departments == snapshot["departments"]


def test_run_canonical_kommun_day_rejects_missing_display_label() -> None:
    context = KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-a",
        site_name="Site A",
        service_date="2026-09-03",
        departments=(KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A"),),
        meal_labels={"lunch": "Lunch", "dinner": "Kvällsmat"},
        lunch_baselines={"unit-a": 10},
        dinner_baselines={"unit-a": 10},
        requirement_projection_by_group_id={"group-a": KommunGroupCompatibilityMetadata(group_id="group-a", diet_name="")},
    )

    with pytest.raises(KommunDayOrchestrationError, match="missing_group_label"):
        run_canonical_kommun_day(context)


def test_run_canonical_kommun_day_blocks_when_shadow_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _business_context()

    def _blocked_shadow(*, meal_key: str, **kwargs: object) -> ProductionShadowRun:
        accepted = meal_key != "lunch"
        return _meal_run(
            meal_key=meal_key,
            baselines={"unit-b": 8, "unit-a": 10} if meal_key == "lunch" else {"unit-b": 5, "unit-a": 7},
            deviations={"unit-a": 1},
            accepted=accepted,
            requirement_group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        )

    monkeypatch.setattr(day_orchestration, "run_canonical_requirement_groups_in_production_shadow", _blocked_shadow)

    with pytest.raises(KommunDayProjectionError, match="blocked_meal_run"):
        run_canonical_kommun_day(context)


def test_run_canonical_kommun_day_does_not_depend_on_alt_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    context = KommunDayBusinessContext(
        tenant_id=1,
        site_id="site-a",
        site_name="Site A",
        service_date="2026-09-03",
        departments=(KommunDepartmentProjectionContext(department_id="unit-a", department_name="Unit A"),),
        meal_labels={"lunch": "Mittdagsmåltid", "dinner": "Kvällsmåltid"},
        lunch_baselines={"unit-a": 10},
        dinner_baselines={"unit-a": 10},
        requirement_projection_by_group_id={"group-a": KommunGroupCompatibilityMetadata(group_id="group-a", diet_name="Compat A")},
    )

    monkeypatch.setattr(
        day_orchestration,
        "run_canonical_requirement_groups_in_production_shadow",
        lambda **kwargs: _meal_run(
            meal_key=str(kwargs["meal_key"]),
            baselines=dict(kwargs["unit_baselines"]),
            deviations={"unit-a": 1},
            requirement_group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 1}],
        ),
    )
    monkeypatch.setattr(
        day_orchestration,
        "project_canonical_kommun_day",
        lambda **kwargs: {
            "site_id": kwargs["site_id"],
            "site_name": kwargs["site_name"],
            "date": kwargs["service_date"],
            "meal_labels": dict(kwargs["meal_labels"]),
            "departments": [],
            "totals": {"lunch": {}, "dinner": {}},
        },
    )

    payload = run_canonical_kommun_day(context)

    assert payload["meal_labels"] == {"lunch": "Mittdagsmåltid", "dinner": "Kvällsmåltid"}


def test_run_canonical_kommun_day_module_has_no_legacy_planera_service_or_db_imports() -> None:
    assert "PlaneraService" not in day_orchestration.__dict__
    assert "get_session" not in day_orchestration.__dict__
    assert "text" not in day_orchestration.__dict__


def test_run_canonical_kommun_day_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _business_context()

    def _fake_shadow(*, meal_key: str, **kwargs: object) -> ProductionShadowRun:
        if meal_key == "lunch":
            return _meal_run(
                meal_key=meal_key,
                baselines={"unit-b": 8, "unit-a": 10},
                deviations={"unit-a": 2},
                requirement_group_refs=[{"group_id": "group-a", "unit_id": "unit-a", "quantity": 2}],
            )
        return _meal_run(
            meal_key=meal_key,
            baselines={"unit-b": 5, "unit-a": 7},
            deviations={"unit-b": 1, "unit-a": 1},
            requirement_group_refs=[
                {"group_id": "group-b", "unit_id": "unit-a", "quantity": 1},
                {"group_id": "group-c", "unit_id": "unit-b", "quantity": 1},
            ],
        )

    def _fake_project(**kwargs: object) -> dict[str, object]:
        return {
            "site_id": kwargs["site_id"],
            "site_name": kwargs["site_name"],
            "date": kwargs["service_date"],
            "meal_labels": dict(kwargs["meal_labels"]),
            "departments": [
                {"department_id": dept.department_id, "department_name": dept.department_name}
                for dept in kwargs["departments"]
            ],
            "totals": {
                "lunch": {
                    "residents_total": 18,
                    "special_diets": [{"diet_type_id": "group:group-a", "diet_name": "Compat A", "count": 2}],
                    "normal_diet_count": 16,
                },
                "dinner": {
                    "residents_total": 12,
                    "special_diets": [
                        {"diet_type_id": "group:group-b", "diet_name": "Compat B", "count": 1},
                        {"diet_type_id": "group:group-c", "diet_name": "Compat C", "count": 1},
                    ],
                    "normal_diet_count": 10,
                },
            },
        }

    monkeypatch.setattr(day_orchestration, "run_canonical_requirement_groups_in_production_shadow", _fake_shadow)
    monkeypatch.setattr(day_orchestration, "project_canonical_kommun_day", _fake_project)

    first = run_canonical_kommun_day(context)
    second = run_canonical_kommun_day(context)

    assert first == second
