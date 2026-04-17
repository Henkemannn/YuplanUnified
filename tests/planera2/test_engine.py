from __future__ import annotations

from core.planera2 import Deviation, PlanRequest, compute_plan


def test_compute_plan_happy_path() -> None:
    request = PlanRequest(
        baseline=50,
        deviations=(
            Deviation(form="timbal", category_key="Ej Fisk", quantity=3),
            Deviation(form="timbal", category_key="laktosfri", quantity=2),
        ),
    )

    result = compute_plan(request)

    assert result.totals == {
        "baseline_total": 50,
        "deviation_total": 5,
        "normal_total": 45,
    }
    assert result.per_form == {"timbal": 5}
    assert result.per_combination == {
        "timbal__ej_fisk": 3,
        "timbal__laktosfri": 2,
    }
    assert result.per_unit == {}
    assert result.warnings == []


def test_compute_plan_multi_category_key_sorted() -> None:
    payload = {
        "baseline": 10,
        "deviations": [
            {
                "form": "Timbal",
                "category_keys": ["Laktosfri", "Ej Fisk"],
                "quantity": 4,
            }
        ],
    }

    result = compute_plan(payload)

    assert result.per_form == {"timbal": 4}
    assert result.per_combination == {"timbal__ej_fisk__laktosfri": 4}


def test_compute_plan_sums_per_unit_when_present() -> None:
    payload = {
        "baseline": 7,
        "deviations": [
            {"form": "flytande", "category_key": "nötfri", "quantity": 2, "unit_id": "A"},
            {"form": "flytande", "category_key": "nötfri", "quantity": 1, "unit_id": "A"},
            {"form": "flytande", "category_key": "nötfri", "quantity": 2, "unit_id": "B"},
        ],
    }

    result = compute_plan(payload)

    assert result.per_unit == {"A": 3, "B": 2}
    assert result.totals["deviation_total"] == 5
    assert result.totals["normal_total"] == 2


def test_compute_plan_deviation_exceeds_baseline_warns_and_clamps() -> None:
    payload = {
        "baseline": 1,
        "deviations": [
            {"form": "timbal", "category_key": "ej_fisk", "quantity": 3},
        ],
    }

    result = compute_plan(payload)

    assert result.totals["normal_total"] == 0
    assert any("Deviation exceeds baseline" in w for w in result.warnings)


def test_compute_plan_invalid_data_warns_but_no_crash() -> None:
    payload = {
        "baseline": -2,
        "deviations": [
            {"form": "", "category_key": "A", "quantity": 1},
            {"form": "Timbal", "category_key": "", "quantity": -4},
            {"form": "Timbal", "quantity": 2},
            "bad-item",
        ],
    }

    result = compute_plan(payload)

    assert result.totals["baseline_total"] == 0
    assert result.totals["deviation_total"] == 2
    assert result.totals["normal_total"] == 0
    assert result.per_combination == {"timbal__unknown_category": 2}
    assert len(result.warnings) >= 4


def test_compute_plan_unknown_categories_warn_when_context_defines_known_set() -> None:
    payload = {
        "baseline": 5,
        "context": {"known_category_keys": ["ej_fisk"]},
        "deviations": [
            {"form": "timbal", "category_key": "okand", "quantity": 1},
        ],
    }

    result = compute_plan(payload)

    assert result.per_combination == {"timbal__okand": 1}
    assert any("Unknown category: okand" in w for w in result.warnings)


def test_compute_plan_empty_input_returns_empty_structure() -> None:
    result = compute_plan({})

    assert result.totals == {
        "baseline_total": 0,
        "deviation_total": 0,
        "normal_total": 0,
    }
    assert result.per_form == {}
    assert result.per_combination == {}
    assert result.per_unit == {}
    assert result.warnings == []


def test_compute_plan_result_is_deterministically_sorted() -> None:
    payload = {
        "baseline": 20,
        "deviations": [
            {"form": "B-form", "category_key": "Zeta", "quantity": 1, "unit_id": "2"},
            {"form": "A-form", "category_key": "Alpha", "quantity": 1, "unit_id": "1"},
        ],
    }

    result = compute_plan(payload)

    assert list(result.per_form.keys()) == ["a_form", "b_form"]
    assert list(result.per_combination.keys()) == ["a_form__alpha", "b_form__zeta"]
    assert list(result.per_unit.keys()) == ["1", "2"]
