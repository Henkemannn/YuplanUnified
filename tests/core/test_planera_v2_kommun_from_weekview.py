from __future__ import annotations

from core.planera_v2.adapters.kommun_from_weekview import build_plan_request_from_weekview_day
from core.planera_v2.domain import Deviation, PlanRequest, UnitInput
from core.planera_v2.engine import compute_plan


class _FakePlaneraService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def compute_day(
        self,
        tenant_id: int | str,
        site_id: str,
        iso_date: str,
        departments: list[tuple[str, str]],
    ) -> dict[str, object]:
        return dict(self._payload)


def test_bridge_maps_unit_baselines_and_effective_day_deviations() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 12,
                        "alt_choice": "Alt1",
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 2},
                            {"diet_type_id": "laktosfri", "count": 1},
                        ],
                    }
                },
            },
            {
                "department_id": "unit_b",
                "meals": {
                    "lunch": {
                        "residents_total": 8,
                        "alt_choice": "Alt2",
                        "special_diets": [
                            {"diet_type_id": "not_fri", "count": 3},
                        ],
                    }
                },
            },
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A"), ("unit_b", "Unit B")],
    )

    assert isinstance(request, PlanRequest)
    assert request.baseline == 20
    assert request.units == [
        UnitInput(unit_id="unit_a", baseline_total=12),
        UnitInput(unit_id="unit_b", baseline_total=8),
    ]
    assert request.deviations == [
        Deviation(form="specialkost", category_keys=["ej_fisk"], quantity=2, unit_id="unit_a"),
        Deviation(form="specialkost", category_keys=["laktosfri"], quantity=1, unit_id="unit_a"),
        Deviation(form="specialkost", category_keys=["not_fri"], quantity=3, unit_id="unit_b"),
    ]
    assert request.context["site_id"] == "site_1"
    assert request.context["date"] == "2026-04-14"
    assert request.context["meal_key"] == "lunch"
    assert request.context["menu_option_by_unit"] == {"unit_a": "Alt1", "unit_b": "Alt2"}


def test_bridge_does_not_use_raw_marks_as_deviations_without_effective_special_counts() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "marks": [
                    {"day_of_week": 2, "meal": "lunch", "diet_type": "ej_fisk", "marked": True}
                ],
                "meals": {
                    "lunch": {
                        "residents_total": 7,
                        # Effective day mapping says no special output today.
                        "special_diets": [],
                    }
                },
            }
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )

    assert request.baseline == 7
    assert request.units == [UnitInput(unit_id="unit_a", baseline_total=7)]
    assert request.deviations == []


def test_bridge_output_is_valid_engine_input_for_single_day_meal() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "dinner": {
                        "residents_total": 10,
                        "special_diets": [
                            {"diet_type_id": "konsistens_timbal", "count": 2},
                        ],
                    }
                },
            },
            {
                "department_id": "unit_b",
                "meals": {
                    "dinner": {
                        "residents_total": 5,
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 1},
                        ],
                    }
                },
            },
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-15",
        meal="dinner",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A"), ("unit_b", "Unit B")],
    )

    result = compute_plan(request)

    assert result.totals.baseline_total == 15
    assert result.totals.deviation_total == 3
    assert result.totals.normal_total == 12
    assert result.per_unit_breakdown["unit_a"].baseline_total == 10
    assert result.per_unit_breakdown["unit_a"].deviation_total == 2
    assert result.per_unit_breakdown["unit_a"].normal_total == 8
    assert result.per_unit_breakdown["unit_b"].baseline_total == 5
    assert result.per_unit_breakdown["unit_b"].deviation_total == 1
    assert result.per_unit_breakdown["unit_b"].normal_total == 4


def test_bridge_supports_dessert_meal_key() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "dessert": {
                        "residents_total": 9,
                        "special_diets": [
                            {"diet_type_id": "sockerreducerad", "count": 2},
                        ],
                    }
                },
            }
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-16",
        meal="dessert",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )

    assert request.baseline == 9
    assert request.units == [UnitInput(unit_id="unit_a", baseline_total=9)]
    assert request.deviations == [
        Deviation(form="specialkost", category_keys=["sockerreducerad"], quantity=2, unit_id="unit_a")
    ]
    assert request.context["meal_key"] == "dessert"


def test_bridge_supports_kvallsmat_alias_to_dinner_data() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "dinner": {
                        "residents_total": 6,
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 1},
                        ],
                    }
                },
            }
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-16",
        meal="kvallsmat",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )

    assert request.baseline == 6
    assert request.units == [UnitInput(unit_id="unit_a", baseline_total=6)]
    assert request.deviations == [
        Deviation(form="specialkost", category_keys=["ej_fisk"], quantity=1, unit_id="unit_a")
    ]


def test_bridge_carries_optional_component_metadata_when_supplied() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 4,
                        "special_diets": [],
                    }
                },
            }
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-16",
        meal="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
        component_id="meatballs",
        component_name="Kottbullar",
        component_role="main",
        component_mode="informational",
    )

    assert request.context["component_id"] == "meatballs"
    assert request.context["component_name"] == "Kottbullar"
    assert request.context["component_role"] == "main"
    assert request.context["component_mode"] == "informational"


def test_bridge_defaults_component_mode_to_informational_when_component_id_exists() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 4,
                        "special_diets": [],
                    }
                },
            }
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-16",
        meal="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
        component_id="fish_timbal",
    )

    assert request.context["component_id"] == "fish_timbal"
    assert request.context["component_mode"] == "informational"


def test_bridge_keeps_component_metadata_absent_when_not_supplied() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 4,
                        "special_diets": [],
                    }
                },
            }
        ]
    }

    request = build_plan_request_from_weekview_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-16",
        meal="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )

    assert "component_id" not in request.context
    assert "component_name" not in request.context
    assert "component_role" not in request.context
    assert "component_mode" not in request.context
