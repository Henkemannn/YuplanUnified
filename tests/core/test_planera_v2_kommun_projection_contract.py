from __future__ import annotations

from core.planera_v2.adapters.kommun_adapter import (
    build_payload_from_kommun_input,
    build_planning_slice_from_kommun_input,
)
from core.planera_v2.engine import compute_plan


def _standard_payload() -> dict[str, object]:
    return {
        "baseline": 10,
        "units": [
            {
                "unit_id": "unit_a",
                "baseline": 10,
            }
        ],
        "context": {"meal_key": "lunch"},
    }


def test_case_a_standard_only_conserves_baseline() -> None:
    planning_slice = build_planning_slice_from_kommun_input(_standard_payload())
    result = compute_plan(planning_slice.to_plan_request())

    assert planning_slice.baseline == 10
    assert planning_slice.deviations == ()
    assert result.totals.baseline_total == 10
    assert result.totals.deviation_total == 0
    assert result.totals.normal_total == 10


def test_case_b_one_requirement_one_marker() -> None:
    planning_slice = build_planning_slice_from_kommun_input(
        {
            "baseline": 1,
            "units": [
                {
                    "unit_id": "unit_a",
                    "baseline": 1,
                    "requirements": [
                        {"form": "texture_soft", "category_keys": ["marker_a"], "quantity": 1},
                    ],
                }
            ],
        }
    )

    assert len(planning_slice.deviations) == 1
    deviation = planning_slice.deviations[0]
    assert deviation.quantity == 1
    assert deviation.category_keys == ["marker_a"]


def test_case_c_simultaneous_requirements_stay_single_demand_unit() -> None:
    planning_slice = build_planning_slice_from_kommun_input(
        {
            "baseline": 1,
            "units": [
                {
                    "unit_id": "unit_a",
                    "baseline": 1,
                    "requirements": [
                        {
                            "form": "texture_soft",
                            "category_keys": ["marker_a", "marker_b"],
                            "quantity": 1,
                        },
                    ],
                }
            ],
        }
    )

    assert len(planning_slice.deviations) == 1
    deviation = planning_slice.deviations[0]
    assert deviation.quantity == 1
    assert deviation.category_keys == ["marker_a", "marker_b"]


def test_case_d_distinct_recipients_become_two_deviations() -> None:
    planning_slice = build_planning_slice_from_kommun_input(
        {
            "baseline": 2,
            "units": [
                {
                    "unit_id": "unit_a",
                    "baseline": 1,
                    "requirements": [
                        {"form": "texture_soft", "category_keys": ["marker_a"], "quantity": 1},
                    ],
                },
                {
                    "unit_id": "unit_b",
                    "baseline": 1,
                    "requirements": [
                        {"form": "texture_soft", "category_keys": ["marker_b"], "quantity": 1},
                    ],
                },
            ],
        }
    )
    result = compute_plan(planning_slice.to_plan_request())

    assert len(planning_slice.deviations) == 2
    assert result.totals.deviation_total == 2
    assert result.per_unit == {"unit_a": 1, "unit_b": 1}


def test_case_e_custom_marker_flows_through_generically() -> None:
    planning_slice = build_planning_slice_from_kommun_input(
        {
            "baseline": 1,
            "units": [
                {
                    "unit_id": "unit_a",
                    "baseline": 1,
                    "requirements": [
                        {"form": "custom_texture", "category_keys": ["custom_marker_x99"], "quantity": 1},
                    ],
                }
            ],
        }
    )
    result = compute_plan(planning_slice.to_plan_request())

    assert planning_slice.deviations[0].category_keys == ["custom_marker_x99"]
    assert result.per_combination == {"custom_texture__custom_marker_x99": 1}


def test_case_f_conservation_for_supported_projection() -> None:
    planning_slice = build_planning_slice_from_kommun_input(
        {
            "baseline": 10,
            "units": [
                {
                    "unit_id": "unit_a",
                    "baseline": 10,
                    "requirements": [
                        {
                            "form": "custom_texture",
                            "category_keys": ["marker_a", "marker_b"],
                            "quantity": 1,
                        },
                    ],
                }
            ],
        }
    )
    result = compute_plan(planning_slice.to_plan_request())

    assert result.totals.baseline_total == 10
    assert result.totals.deviation_total == 1
    assert result.totals.normal_total == 9
    assert result.totals.baseline_total == result.totals.deviation_total + result.totals.normal_total


def test_case_g_aggregate_only_input_is_marked_ambiguous() -> None:
    planning_slice = build_planning_slice_from_kommun_input(
        {
            "baseline": 10,
            "units": [
                {
                    "unit_id": "unit_a",
                    "baseline": 10,
                    "aggregate_category_totals": {"marker_a": 3, "marker_b": 2},
                }
            ],
        }
    )
    payload = build_payload_from_kommun_input(
        {
            "baseline": 10,
            "units": [
                {
                    "unit_id": "unit_a",
                    "baseline": 10,
                    "aggregate_category_totals": {"marker_a": 3, "marker_b": 2},
                }
            ],
        }
    )

    assert planning_slice.compatibility_status == "ambiguous"
    assert planning_slice.deviations == ()
    assert planning_slice.warnings
    assert payload["context"]["compatibility_status"] == "ambiguous"
    assert payload["context"]["compatibility_warnings"]


def test_case_h_deterministic_output_for_equivalent_input() -> None:
    payload_a = {
        "baseline": 3,
        "units": [
            {
                "unit_id": "unit_b",
                "baseline": 1,
                "requirements": [
                    {"form": "texture_soft", "category_keys": ["marker_b"], "quantity": 1},
                ],
            },
            {
                "unit_id": "unit_a",
                "baseline": 2,
                "requirements": [
                    {"form": "texture_soft", "category_keys": ["marker_a"], "quantity": 1},
                ],
            },
        ],
    }
    payload_b = {
        "baseline": 3,
        "units": [
            {
                "unit_id": "unit_a",
                "baseline": 2,
                "requirements": [
                    {"form": "texture_soft", "category_keys": ["marker_a"], "quantity": 1},
                ],
            },
            {
                "unit_id": "unit_b",
                "baseline": 1,
                "requirements": [
                    {"form": "texture_soft", "category_keys": ["marker_b"], "quantity": 1},
                ],
            },
        ],
    }

    slice_a = build_planning_slice_from_kommun_input(payload_a)
    slice_b = build_planning_slice_from_kommun_input(payload_b)

    assert slice_a == slice_b
    assert [unit.unit_id for unit in slice_a.units] == ["unit_a", "unit_b"]
    assert [deviation.unit_id for deviation in slice_a.deviations] == ["unit_a", "unit_b"]
