from __future__ import annotations

from core.planera_v2.adapters.kommun_adapter import build_payload_from_kommun_input


def _kommun_input() -> dict[str, object]:
    return {
        "baseline": 50,
        "meal_key": "lunch",
        "units": [
            {
                "unit_id": "avd_a",
                "baseline": 20,
                "deviations": [
                    {"form": "timbal", "category_keys": ["ej_fisk"], "quantity": 2},
                    {"form": "timbal", "category_keys": ["laktosfri"], "quantity": 1},
                ],
            },
            {
                "unit_id": "avd_b",
                "baseline": 30,
                "deviations": [
                    {"form": "flytande", "category_keys": ["ej_fisk"], "quantity": 1},
                ],
            },
        ],
        "context": {
            "menu_option_by_unit": {
                "avd_a": "alt_1",
                "avd_b": "alt_2",
            }
        },
    }


def test_adapter_builds_expected_payload() -> None:
    payload = build_payload_from_kommun_input(_kommun_input())

    assert payload["baseline"] == 50
    assert payload["units"] == [
        {"unit_id": "avd_a", "baseline_total": 20},
        {"unit_id": "avd_b", "baseline_total": 30},
    ]
    assert payload["deviations"] == [
        {"form": "timbal", "category_keys": ["ej_fisk"], "quantity": 2, "unit_id": "avd_a"},
        {"form": "timbal", "category_keys": ["laktosfri"], "quantity": 1, "unit_id": "avd_a"},
        {"form": "flytande", "category_keys": ["ej_fisk"], "quantity": 1, "unit_id": "avd_b"},
    ]


def test_adapter_preserves_unit_id_and_context() -> None:
    payload = build_payload_from_kommun_input(_kommun_input())

    assert all(deviation["unit_id"] in {"avd_a", "avd_b"} for deviation in payload["deviations"])
    assert payload["context"] == {
        "menu_option_by_unit": {"avd_a": "alt_1", "avd_b": "alt_2"},
        "meal_key": "lunch",
    }


def test_adapter_aggregates_baseline_from_units_when_missing() -> None:
    data = _kommun_input()
    data.pop("baseline")

    payload = build_payload_from_kommun_input(data)

    assert payload["baseline"] == 50


def test_adapter_handles_empty_units_safely() -> None:
    payload = build_payload_from_kommun_input({"meal_key": "lunch", "units": [], "context": {}})

    assert payload == {"baseline": 0, "units": [], "deviations": [], "context": {"meal_key": "lunch"}}


def test_adapter_carries_optional_component_metadata_into_context() -> None:
    payload = build_payload_from_kommun_input(
        {
            "meal_key": "lunch",
            "component_id": "meatballs",
            "component_name": "Kottbullar",
            "units": [],
            "context": {},
        }
    )

    assert payload["context"] == {
        "meal_key": "lunch",
        "component_id": "meatballs",
        "component_name": "Kottbullar",
        "component_mode": "informational",
    }


def test_adapter_carries_component_role_and_mode_when_supplied() -> None:
    payload = build_payload_from_kommun_input(
        {
            "meal_key": "lunch",
            "component_id": "mayonnaise_sauce",
            "component_name": "Majonnassas",
            "component_role": "sauce",
            "component_mode": "informational",
            "units": [],
            "context": {},
        }
    )

    assert payload["context"] == {
        "meal_key": "lunch",
        "component_id": "mayonnaise_sauce",
        "component_name": "Majonnassas",
        "component_role": "sauce",
        "component_mode": "informational",
    }
