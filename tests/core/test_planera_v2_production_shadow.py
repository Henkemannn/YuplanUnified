from __future__ import annotations

from copy import deepcopy

import pytest

from core.planera_v2 import shadow
from core.planera_v2.acceptance import ProductionAcceptanceResult
from core.planera_v2.domain import Deviation, PlanRequest, PlanResult, PlanningSlice, Totals, UnitInput


def _unit(unit_id: str, baseline_total: int) -> UnitInput:
    return UnitInput(unit_id=unit_id, baseline_total=baseline_total)


def _deviation(
    form: str,
    category_keys: list[str],
    quantity: int,
    unit_id: str | None = None,
) -> Deviation:
    return Deviation(form=form, category_keys=category_keys, quantity=quantity, unit_id=unit_id)


def _plan_result(baseline_total: int, deviation_total: int = 0) -> PlanResult:
    normal_total = baseline_total - deviation_total
    return PlanResult(
        totals=Totals(
            baseline_total=baseline_total,
            deviation_total=deviation_total,
            normal_total=normal_total,
        ),
        per_form={"form_a": deviation_total} if deviation_total else {},
        per_combination={"form_a__category_a__category_b": deviation_total} if deviation_total else {},
        per_unit={"unit-a": deviation_total} if deviation_total else {},
        per_unit_breakdown={},
        warnings=[],
    )


def test_valid_generic_plan_request_passes_and_computes_diagnostics() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 3, "unit-a")],
    )

    run = shadow.run_plan_request_in_production_shadow(request)

    assert run.production_acceptance_verdict == "PASS"
    assert run.is_production_accepted is True
    assert run.acceptance == ProductionAcceptanceResult(accepted=True, issues=())
    assert run.diagnostic_result is not None
    assert run.diagnostic_result.totals.baseline_total == 10
    assert run.diagnostic_result.totals.deviation_total == 3


def test_shadow_run_verdict_derives_from_acceptance_only() -> None:
    accepted_run = shadow.ProductionShadowRun(
        request=PlanRequest(baseline=0),
        acceptance=ProductionAcceptanceResult(accepted=True, issues=()),
        diagnostic_result=None,
    )
    blocked_run = shadow.ProductionShadowRun(
        request=PlanRequest(baseline=0),
        acceptance=ProductionAcceptanceResult(accepted=False, issues=()),
        diagnostic_result=None,
    )

    assert accepted_run.production_acceptance_verdict == "PASS"
    assert accepted_run.is_production_accepted is True
    assert blocked_run.production_acceptance_verdict == "BLOCKED"
    assert blocked_run.is_production_accepted is False


def test_blocked_request_keeps_acceptance_authoritative_and_computes_diagnostics_when_enabled() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 2, "unit-a")],
    )

    run = shadow.run_plan_request_in_production_shadow(request, expected_unit_ids=["unit-a", "unit-b"])

    assert run.production_acceptance_verdict == "BLOCKED"
    assert run.is_production_accepted is False
    assert [issue.code for issue in run.acceptance.issues] == ["expected_unit_missing"]
    assert run.diagnostic_result is not None
    assert run.diagnostic_result.totals.baseline_total == 10


def test_blocked_request_with_diagnostics_disabled_skips_compute_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []

    def _boom(*args: object, **kwargs: object) -> PlanResult:
        called.append(True)
        raise AssertionError("compute_plan should not be called")

    monkeypatch.setattr(shadow, "compute_plan", _boom)

    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 2, "unit-a")],
    )

    run = shadow.run_plan_request_in_production_shadow(
        request,
        expected_unit_ids=["unit-a", "unit-b"],
        compute_diagnostics_when_blocked=False,
    )

    assert called == []
    assert run.production_acceptance_verdict == "BLOCKED"
    assert run.diagnostic_result is None


def test_accepted_request_always_computes(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _plan_result(10, 3)
    called: list[PlanRequest] = []

    def _accept(request: PlanRequest, *, expected_unit_ids=None) -> ProductionAcceptanceResult:
        return ProductionAcceptanceResult(accepted=True, issues=())

    def _compute(request: PlanRequest) -> PlanResult:
        called.append(request)
        return result

    monkeypatch.setattr(shadow, "validate_plan_request_for_production", _accept)
    monkeypatch.setattr(shadow, "compute_plan", _compute)

    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 3, "unit-a")],
    )

    run = shadow.run_plan_request_in_production_shadow(request)

    assert called == [request]
    assert run.production_acceptance_verdict == "PASS"
    assert run.diagnostic_result == result


def test_expected_unit_ids_are_passed_through_to_acceptance(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[tuple[str, ...] | None] = []

    def _accept(request: PlanRequest, *, expected_unit_ids=None) -> ProductionAcceptanceResult:
        if expected_unit_ids is None:
            observed.append(None)
        else:
            observed.append(tuple(expected_unit_ids))
        return ProductionAcceptanceResult(accepted=True, issues=())

    monkeypatch.setattr(shadow, "validate_plan_request_for_production", _accept)
    monkeypatch.setattr(shadow, "compute_plan", lambda request: _plan_result(10, 0))

    request = PlanRequest(baseline=10, units=[_unit("unit-a", 10)])

    shadow.run_plan_request_in_production_shadow(request, expected_unit_ids=["unit-a", "unit-b"])

    assert observed == [("unit-a", "unit-b")]


def test_authoritative_baseline_mismatch_blocks_shadow_run() -> None:
    request = PlanRequest(
        baseline=11,
        units=[_unit("unit-a", 5), _unit("unit-b", 5)],
    )

    run = shadow.run_plan_request_in_production_shadow(request, expected_unit_ids=["unit-a", "unit-b"])

    assert run.production_acceptance_verdict == "BLOCKED"
    assert [issue.code for issue in run.acceptance.issues] == ["unit_baseline_sum_mismatch"]
    assert run.diagnostic_result is not None


def test_missing_expected_unit_blocks_shadow_run() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
    )

    run = shadow.run_plan_request_in_production_shadow(request, expected_unit_ids=["unit-a", "unit-b"])

    assert run.production_acceptance_verdict == "BLOCKED"
    assert [issue.code for issue in run.acceptance.issues] == ["expected_unit_missing"]


def test_malformed_positive_deviation_blocks_shadow_run() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("", ["category-a"], 2, "unit-a")],
    )

    run = shadow.run_plan_request_in_production_shadow(request)

    assert run.production_acceptance_verdict == "BLOCKED"
    assert [issue.code for issue in run.acceptance.issues] == ["deviation_form_missing"]


def test_unknown_deviation_unit_blocks_shadow_run() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 2, "unit-b")],
    )

    run = shadow.run_plan_request_in_production_shadow(request)

    assert run.production_acceptance_verdict == "BLOCKED"
    assert [issue.code for issue in run.acceptance.issues] == ["deviation_unit_unknown"]


def test_valid_multi_key_deviation_counts_once_in_diagnostics() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a", "category-b"], 5, "unit-a")],
    )

    run = shadow.run_plan_request_in_production_shadow(request)

    assert run.production_acceptance_verdict == "PASS"
    assert run.diagnostic_result is not None
    assert run.diagnostic_result.totals.deviation_total == 5
    assert run.diagnostic_result.per_combination == {"form_a__category_a__category_b": 5}


def test_canonical_requirement_group_wrapper_passes_with_expected_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict[str, object]] = []
    planning_slice = PlanningSlice(
        baseline=20,
        units=(
            _unit("unit-a", 10),
            _unit("unit-b", 10),
        ),
        deviations=(
            _deviation("form-a", ["category-a"], 3, "unit-a"),
            _deviation("form-b", ["category-b"], 2, "unit-b"),
        ),
        context={"source": "canonical_requirement_groups"},
        warnings=(),
        compatibility_status="resolved",
    )

    def _build_slice(**kwargs: object) -> PlanningSlice:
        captured.append(kwargs)
        return planning_slice

    monkeypatch.setattr(shadow, "build_planning_slice_from_requirement_groups", _build_slice)

    run = shadow.run_canonical_requirement_groups_in_production_shadow(
        site_id="site-a",
        service_date="2026-09-03",
        meal_key="lunch",
        unit_baselines={"unit-a": 10, "unit-b": 10},
        expected_unit_ids=["unit-a", "unit-b"],
    )

    assert captured == [
        {
            "site_id": "site-a",
            "service_date": "2026-09-03",
            "meal_key": "lunch",
            "unit_baselines": {"unit-a": 10, "unit-b": 10},
            "context": None,
        }
    ]
    assert run.production_acceptance_verdict == "PASS"
    assert run.diagnostic_result is not None
    assert run.diagnostic_result.totals.baseline_total == 20
    assert run.diagnostic_result.totals.deviation_total == 5


def test_canonical_wrapper_blocks_with_incomplete_expected_unit_set(monkeypatch: pytest.MonkeyPatch) -> None:
    planning_slice = PlanningSlice(
        baseline=20,
        units=(
            _unit("unit-a", 10),
            _unit("unit-b", 10),
        ),
        deviations=(),
        context={},
        warnings=(),
        compatibility_status="resolved",
    )

    monkeypatch.setattr(shadow, "build_planning_slice_from_requirement_groups", lambda **kwargs: planning_slice)

    run = shadow.run_canonical_requirement_groups_in_production_shadow(
        site_id="site-a",
        service_date="2026-09-03",
        meal_key="lunch",
        unit_baselines={"unit-a": 10, "unit-b": 10},
        expected_unit_ids=["unit-a"],
    )

    assert run.production_acceptance_verdict == "BLOCKED"
    assert [issue.code for issue in run.acceptance.issues] == ["unexpected_unit"]


def test_canonical_wrapper_blocks_with_mismatched_authoritative_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    planning_slice = PlanningSlice(
        baseline=21,
        units=(
            _unit("unit-a", 10),
            _unit("unit-b", 10),
        ),
        deviations=(),
        context={},
        warnings=(),
        compatibility_status="resolved",
    )

    monkeypatch.setattr(shadow, "build_planning_slice_from_requirement_groups", lambda **kwargs: planning_slice)

    run = shadow.run_canonical_requirement_groups_in_production_shadow(
        site_id="site-a",
        service_date="2026-09-03",
        meal_key="lunch",
        unit_baselines={"unit-a": 10, "unit-b": 10},
        expected_unit_ids=["unit-a", "unit-b"],
    )

    assert run.production_acceptance_verdict == "BLOCKED"
    assert [issue.code for issue in run.acceptance.issues] == ["unit_baseline_sum_mismatch"]


def test_canonical_wrapper_does_not_query_departments_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[dict[str, object]] = []
    planning_slice = PlanningSlice(
        baseline=10,
        units=(_unit("unit-a", 10),),
        deviations=(),
        context={},
        warnings=(),
        compatibility_status="resolved",
    )

    def _build_slice(**kwargs: object) -> PlanningSlice:
        called.append(kwargs)
        return planning_slice

    monkeypatch.setattr(shadow, "build_planning_slice_from_requirement_groups", _build_slice)

    run = shadow.run_canonical_requirement_groups_in_production_shadow(
        site_id="site-a",
        service_date="2026-09-03",
        meal_key="lunch",
        unit_baselines={"unit-a": 10},
        expected_unit_ids=["unit-a"],
    )

    assert called == [
        {
            "site_id": "site-a",
            "service_date": "2026-09-03",
            "meal_key": "lunch",
            "unit_baselines": {"unit-a": 10},
            "context": None,
        }
    ]
    assert run.production_acceptance_verdict == "PASS"


def test_shadow_orchestration_does_not_mutate_plan_request() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 1, "unit-a")],
        context={"keep": [1, 2, 3]},
    )
    before = deepcopy(request)

    run = shadow.run_plan_request_in_production_shadow(request)

    assert run.production_acceptance_verdict == "PASS"
    assert request == before


def test_deterministic_acceptance_issue_order_is_preserved() -> None:
    request = PlanRequest(
        baseline=1,
        units=[_unit("unit-a", 1), _unit("unit-a", 2), _unit(" ", 3), _unit("unit-b", -1)],
        deviations=[
            _deviation("", [], -1, "unit-c"),
            _deviation("form-a", [], 2, "unit-b"),
        ],
    )

    run = shadow.run_plan_request_in_production_shadow(request, expected_unit_ids=["unit-a", "unit-b", "unit-d"])

    assert [issue.code for issue in run.acceptance.issues] == [
        "duplicate_unit_id",
        "unit_id_empty",
        "unit_baseline_negative",
        "expected_unit_missing",
        "deviation_quantity_negative",
        "deviation_unit_unknown",
        "deviation_form_missing",
        "deviation_category_missing",
        "deviation_category_missing",
    ]