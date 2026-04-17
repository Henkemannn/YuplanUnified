from __future__ import annotations

from core.planera_v2.domain import Deviation, PlanRequest, UnitInput
from core.planera_v2.dev_runner import format_dev_run_report, run_planera_v2_from_current_day


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


def test_dev_runner_passes_bridge_output_and_returns_engine_result() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 12,
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 2},
                            {"diet_type_id": "laktosfri", "count": 1},
                        ],
                    }
                },
            }
        ]
    }

    run = run_planera_v2_from_current_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )

    assert run.request.baseline == 12
    assert run.request.units == [UnitInput(unit_id="unit_a", baseline_total=12)]
    assert run.request.deviations == [
        Deviation(form="specialkost", category_keys=["ej_fisk"], quantity=2, unit_id="unit_a"),
        Deviation(form="specialkost", category_keys=["laktosfri"], quantity=1, unit_id="unit_a"),
    ]

    assert run.result.totals.baseline_total == 12
    assert run.result.totals.deviation_total == 3
    assert run.result.totals.normal_total == 9


def test_dev_runner_formatter_outputs_are_non_empty_and_have_expected_sections() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "dessert": {
                        "residents_total": 5,
                        "special_diets": [
                            {"diet_type_id": "sockerreducerad", "count": 1},
                        ],
                    }
                },
            }
        ]
    }

    run = run_planera_v2_from_current_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-16",
        meal_key="dessert",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )

    assert run.formatted_debug
    assert run.formatted_clean
    assert run.formatted_kitchen

    assert "Totals:" in run.formatted_debug
    assert "Plan Result" in run.formatted_clean
    assert "TOTAL" in run.formatted_kitchen


def test_dev_runner_report_includes_context_units_and_deviations_sections() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 6,
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 2},
                        ],
                    }
                },
            }
        ]
    }

    run = run_planera_v2_from_current_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-17",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )
    report = format_dev_run_report(run)

    assert "Planera 2.0 Dev Run" in report
    assert "Units:" in report
    assert "Deviations:" in report
    assert "=== Debug Formatter ===" in report
    assert "=== Clean Formatter ===" in report
    assert "=== Kitchen Formatter ===" in report


def test_dev_runner_report_shows_component_metadata_when_present() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 6,
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 1},
                        ],
                    }
                },
            }
        ]
    }

    run = run_planera_v2_from_current_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-17",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
        component_id="meatballs",
        component_name="Kottbullar",
        component_role="main",
    )
    report = format_dev_run_report(run)

    assert "component_id: meatballs" in report
    assert "component_name: Kottbullar" in report
    assert "component_role: main" in report
    assert "component_mode: informational" in report


def test_engine_totals_unchanged_when_component_context_is_present() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 12,
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 2},
                            {"diet_type_id": "laktosfri", "count": 1},
                        ],
                    }
                },
            }
        ]
    }

    base_run = run_planera_v2_from_current_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )
    component_run = run_planera_v2_from_current_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
        component_id="meatballs",
        component_name="Kottbullar",
        component_role="main",
    )

    assert component_run.result.totals == base_run.result.totals
    assert component_run.result.per_form == base_run.result.per_form
    assert component_run.result.per_combination == base_run.result.per_combination
