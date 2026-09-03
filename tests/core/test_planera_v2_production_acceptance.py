from __future__ import annotations

from copy import deepcopy

import pytest

from core.planera_v2.acceptance import (
    ProductionAcceptanceResult,
    validate_plan_request_for_production,
)
from core.planera_v2.domain import Deviation, PlanRequest, UnitInput


def _unit(unit_id: str, baseline_total: int) -> UnitInput:
    return UnitInput(unit_id=unit_id, baseline_total=baseline_total)


def _deviation(
    form: str,
    category_keys: list[str],
    quantity: int,
    unit_id: str | None = None,
) -> Deviation:
    return Deviation(form=form, category_keys=category_keys, quantity=quantity, unit_id=unit_id)


def test_clean_single_unit_request_is_accepted() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 3, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result == ProductionAcceptanceResult(accepted=True, issues=())


def test_clean_multi_unit_request_is_accepted() -> None:
    request = PlanRequest(
        baseline=20,
        units=[_unit("unit-a", 10), _unit("unit-b", 10)],
        deviations=[
            _deviation("form-a", ["category-a"], 3, "unit-a"),
            _deviation("form-b", ["category-b"], 2, "unit-b"),
        ],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is True
    assert result.issues == ()





def test_duplicate_unit_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 5), _unit("unit-a", 6)],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["duplicate_unit_id"]


def test_blank_unit_id_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("   ", 5)],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unit_id_empty"]


def test_negative_unit_baseline_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", -1)],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unit_baseline_negative"]


def test_deviation_with_unknown_unit_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], 2, "unit-b")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["deviation_unit_unknown"]


def test_malformed_positive_deviation_missing_form_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("", ["category-a"], 2, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["deviation_form_missing"]


def test_malformed_positive_deviation_missing_category_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", [], 2, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["deviation_category_missing"]


def test_malformed_positive_deviation_unknown_unit_still_reports_unknown_unit() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("", [], 2, "unit-b")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == [
        "deviation_unit_unknown",
        "deviation_form_missing",
        "deviation_category_missing",
    ]


def test_negative_deviation_quantity_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
        deviations=[_deviation("form-a", ["category-a"], -1, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["deviation_quantity_negative"]


def test_expected_empty_unit_set_rejects_actual_unit() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=[])

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unexpected_unit"]


def test_expected_none_allows_actual_unit_without_expected_set_rejection() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=None)

    assert result.accepted is True
    assert result.issues == ()


def test_authoritative_units_matching_baseline_sum_are_accepted() -> None:
    request = PlanRequest(
        baseline=20,
        units=[_unit("a", 10), _unit("b", 10)],
        deviations=[],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=["a", "b"])

    assert result.accepted is True
    assert result.issues == ()


def test_authoritative_units_baseline_sum_too_high_is_rejected() -> None:
    request = PlanRequest(
        baseline=30,
        units=[_unit("a", 10), _unit("b", 10)],
        deviations=[],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=["a", "b"])

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unit_baseline_sum_mismatch"]


def test_authoritative_units_baseline_sum_too_low_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("a", 10), _unit("b", 10)],
        deviations=[],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=["a", "b"])

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unit_baseline_sum_mismatch"]


def test_same_mismatch_without_expected_unit_contract_stays_generic() -> None:
    request = PlanRequest(
        baseline=30,
        units=[_unit("a", 10), _unit("b", 10)],
        deviations=[],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=None)

    assert result.accepted is True
    assert result.issues == ()


def test_authoritative_empty_population_with_zero_baseline_is_accepted() -> None:
    request = PlanRequest(
        baseline=0,
        units=[],
        deviations=[],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=[])

    assert result.accepted is True
    assert result.issues == ()


def test_authoritative_empty_population_with_nonzero_baseline_is_rejected() -> None:
    request = PlanRequest(
        baseline=5,
        units=[],
        deviations=[],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=[])

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unit_baseline_sum_mismatch"]


def test_valid_deviations_do_not_alter_baseline_equality_result() -> None:
    request = PlanRequest(
        baseline=20,
        units=[_unit("a", 10), _unit("b", 10)],
        deviations=[
            _deviation("form-a", ["category-a"], 3, "a"),
            _deviation("form-b", ["category-b"], 2, "b"),
        ],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=["a", "b"])

    assert result.accepted is True
    assert result.issues == ()


def test_unit_deviation_overflow_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 2)],
        deviations=[_deviation("form-a", ["category-a"], 3, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unit_deviation_exceeds_baseline"]


def test_global_overflow_is_rejected() -> None:
    request = PlanRequest(
        baseline=4,
        units=[_unit("unit-a", 4)],
        deviations=[_deviation("form-a", ["category-a"], 5, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["deviation_exceeds_baseline", "unit_deviation_exceeds_baseline"]


def test_negative_global_baseline_is_rejected_specifically() -> None:
    request = PlanRequest(
        baseline=-1,
        units=[],
        deviations=[],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["global_baseline_negative"]


def test_negative_global_baseline_does_not_emit_overflow_only_because_baseline_is_invalid() -> None:
    request = PlanRequest(
        baseline=-1,
        units=[],
        deviations=[],
    )

    result = validate_plan_request_for_production(request)

    assert "deviation_exceeds_baseline" not in [issue.code for issue in result.issues]


def test_expected_unit_missing_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10)],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=["unit-a", "unit-b"])

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["expected_unit_missing"]
    assert result.issues[0].unit_id == "unit-b"


def test_unexpected_unit_is_rejected() -> None:
    request = PlanRequest(
        baseline=10,
        units=[_unit("unit-a", 10), _unit("unit-b", 0)],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=["unit-a"])

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["unexpected_unit"]
    assert result.issues[0].unit_id == "unit-b"


def test_zero_baseline_and_zero_deviations_are_accepted() -> None:
    request = PlanRequest(
        baseline=0,
        units=[_unit("unit-a", 0)],
        deviations=[],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is True
    assert result.issues == ()


def test_multi_key_cohort_quantity_counts_once() -> None:
    request = PlanRequest(
        baseline=5,
        units=[_unit("unit-a", 5)],
        deviations=[_deviation("form-a", ["category-a", "category-b"], 5, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is True
    assert result.issues == ()


def test_global_only_request_with_unassigned_positive_deviation_is_accepted() -> None:
    request = PlanRequest(
        baseline=5,
        units=[],
        deviations=[_deviation("form-a", ["category-a"], 3)],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is True
    assert result.issues == ()


def test_unassigned_positive_deviation_with_authoritative_units_is_rejected() -> None:
    request = PlanRequest(
        baseline=5,
        units=[_unit("unit-a", 5)],
        deviations=[_deviation("form-a", ["category-a"], 3)],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is False
    assert [issue.code for issue in result.issues] == ["deviation_unit_missing"]


def test_zero_quantity_unassigned_deviation_does_not_block_by_itself() -> None:
    request = PlanRequest(
        baseline=5,
        units=[_unit("unit-a", 5)],
        deviations=[_deviation("form-a", ["category-a"], 0)],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is True
    assert result.issues == ()


def test_issue_order_is_deterministic() -> None:
    request = PlanRequest(
        baseline=1,
        units=[_unit("unit-a", 1), _unit("unit-a", 2), _unit(" ", 3), _unit("unit-b", -1)],
        deviations=[
            _deviation("", [], -1, "unit-c"),
            _deviation("form-a", [], 2, "unit-b"),
        ],
    )

    result = validate_plan_request_for_production(request, expected_unit_ids=["unit-a", "unit-b", "unit-d"])

    assert [issue.code for issue in result.issues] == [
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


def test_validator_does_not_mutate_plan_request() -> None:
    request = PlanRequest(
        baseline=8,
        units=[_unit("unit-a", 5), _unit("unit-b", 3)],
        deviations=[_deviation("form-a", ["category-a"], 2, "unit-a")],
        context={"keep": [1, 2, 3]},
    )
    before = deepcopy(request)

    result = validate_plan_request_for_production(request, expected_unit_ids=["unit-a", "unit-b"])

    assert result.accepted is True
    assert request == before


def test_validator_does_not_depend_on_engine_compute_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.planera_v2 import engine

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("compute_plan should not be called")

    monkeypatch.setattr(engine, "compute_plan", _boom)

    request = PlanRequest(
        baseline=6,
        units=[_unit("unit-a", 6)],
        deviations=[_deviation("form-a", ["category-a"], 2, "unit-a")],
    )

    result = validate_plan_request_for_production(request)

    assert result.accepted is True
    assert result.issues == ()