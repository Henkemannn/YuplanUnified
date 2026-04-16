from __future__ import annotations

from core.planera_v2.domain import Deviation, PlanRequest, Totals, UnitBreakdown
from core.planera_v2.engine import compute_plan


def test_normal_example() -> None:
    request = PlanRequest(
        baseline=50,
        deviations=[
            Deviation(form="timbal", category_keys=["ej_fisk"], quantity=3),
            Deviation(form="timbal", category_keys=["laktosfri"], quantity=2),
        ],
    )

    result = compute_plan(request)

    assert result.totals == Totals(baseline_total=50, deviation_total=5, normal_total=45)
    assert result.per_form == {"timbal": 5}
    assert result.per_combination == {
        "timbal__ej_fisk": 3,
        "timbal__laktosfri": 2,
    }
    assert result.per_unit == {}
    assert result.per_unit_breakdown == {}
    assert result.warnings == []


def test_multiple_category_key_sort_order() -> None:
    request = PlanRequest(
        baseline=20,
        deviations=[
            Deviation(form="Timbal", category_keys=["Laktosfri", "Ej Fisk"], quantity=4),
        ],
    )

    result = compute_plan(request)

    assert result.per_combination == {"timbal__ej_fisk__laktosfri": 4}


def test_negative_baseline_clamps_to_zero_with_warning() -> None:
    request = PlanRequest(
        baseline=-1,
        deviations=[
            Deviation(form="timbal", category_keys=["ej_fisk"], quantity=1),
        ],
    )

    result = compute_plan(request)

    assert result.totals.baseline_total == 0
    assert "baseline < 0 clamped to 0" in result.warnings


def test_normalization_of_key_values() -> None:
    request = PlanRequest(
        baseline=3,
        deviations=[
            Deviation(form=" Timbal ", category_keys=[" Ej-Fisk "], quantity=1),
        ],
    )

    result = compute_plan(request)

    assert result.per_form == {"timbal": 1}
    assert result.per_combination == {"timbal__ej_fisk": 1}


def test_deviation_exceeds_baseline_clamps_to_zero_with_warning() -> None:
    request = PlanRequest(
        baseline=2,
        deviations=[
            Deviation(form="flytande", category_keys=["ej_fisk"], quantity=3),
        ],
    )

    result = compute_plan(request)

    assert result.totals.normal_total == 0
    assert "deviation exceeds baseline; normal_total clamped to 0" in result.warnings


def test_empty_input_returns_stable_empty_structure() -> None:
    result = compute_plan(PlanRequest())

    assert result.totals == Totals(baseline_total=0, deviation_total=0, normal_total=0)
    assert result.per_form == {}
    assert result.per_combination == {}
    assert result.per_unit == {}
    assert result.warnings == []


def test_missing_category_keys_policy_skips_deviation_with_warning() -> None:
    request = PlanRequest(
        baseline=10,
        deviations=[
            Deviation(form="timbal", category_keys=[], quantity=2),
        ],
    )

    result = compute_plan(request)

    assert any("missing category_key" in warning for warning in result.warnings)
    assert result.totals.deviation_total == 0
    assert result.per_form == {}
    assert result.per_combination == {}
    assert result.per_unit_breakdown == {}
    assert result.totals.normal_total == 10


def test_per_unit_breakdown_exact_values_without_inferred_baseline_or_normal() -> None:
    request = PlanRequest(
        baseline=25,
        deviations=[
            Deviation(form="Timbal", category_keys=["Ej Fisk"], quantity=2, unit_id="avd_a"),
            Deviation(form="Flytande", category_keys=["Laktosfri"], quantity=1, unit_id="avd_a"),
            Deviation(form="Timbal", category_keys=["Laktosfri"], quantity=3, unit_id="avd_b"),
            Deviation(form="Flytande", category_keys=[], quantity=9, unit_id="avd_b"),
        ],
    )

    result = compute_plan(request)

    assert result.totals == Totals(baseline_total=25, deviation_total=6, normal_total=19)
    assert result.per_unit == {"avd_a": 3, "avd_b": 3}

    assert result.per_unit_breakdown == {
        "avd_a": UnitBreakdown(
            baseline_total=0,
            deviation_total=3,
            normal_total=0,
            per_combination={
                "flytande__laktosfri": 1,
                "timbal__ej_fisk": 2,
            },
            per_form={
                "flytande": 1,
                "timbal": 2,
            },
        ),
        "avd_b": UnitBreakdown(
            baseline_total=0,
            deviation_total=3,
            normal_total=0,
            per_combination={
                "timbal__laktosfri": 3,
            },
            per_form={
                "timbal": 3,
            },
        ),
    }
