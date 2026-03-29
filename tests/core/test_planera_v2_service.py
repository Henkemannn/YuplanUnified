from __future__ import annotations

from core.planera_v2.domain import PlanRequest
from core.planera_v2.service import (
    build_plan_request_from_adapter_payload,
    run_plan_from_payload,
)


def _sample_payload() -> dict[str, object]:
    return {
        "baseline": 50,
        "deviations": [
            {
                "form": "timbal",
                "category_keys": ["ej_fisk"],
                "quantity": 2,
                "unit_id": "avd_a",
            },
            {
                "form": "timbal",
                "category_keys": ["laktosfri"],
                "quantity": 1,
                "unit_id": "avd_a",
            },
            {
                "form": "flytande",
                "category_keys": ["ej_fisk"],
                "quantity": 1,
                "unit_id": "avd_b",
            },
        ],
        "context": {
            "menu_option_by_unit": {"avd_a": "alt_1", "avd_b": "alt_2"},
            "meal_key": "lunch",
        },
    }


def test_run_plan_from_payload_returns_expected_plan_result() -> None:
    result = run_plan_from_payload(_sample_payload())

    assert result.totals.baseline_total == 50
    assert result.totals.deviation_total == 4
    assert result.totals.normal_total == 46
    assert result.per_form == {"flytande": 1, "timbal": 3}
    assert result.per_combination == {
        "flytande__ej_fisk": 1,
        "timbal__ej_fisk": 2,
        "timbal__laktosfri": 1,
    }
    assert result.per_unit == {"avd_a": 3, "avd_b": 1}


def test_build_plan_request_from_adapter_payload_creates_domain_request() -> None:
    request = build_plan_request_from_adapter_payload(_sample_payload())

    assert isinstance(request, PlanRequest)
    assert request.baseline == 50
    assert request.context == {
        "menu_option_by_unit": {"avd_a": "alt_1", "avd_b": "alt_2"},
        "meal_key": "lunch",
    }
    assert len(request.deviations) == 3
    assert request.deviations[0].form == "timbal"
    assert request.deviations[0].category_keys == ["ej_fisk"]
    assert request.deviations[0].quantity == 2
    assert request.deviations[0].unit_id == "avd_a"


def test_service_is_deterministic_for_same_payload() -> None:
    payload = _sample_payload()

    result_1 = run_plan_from_payload(payload)
    result_2 = run_plan_from_payload(payload)

    assert result_1 == result_2
