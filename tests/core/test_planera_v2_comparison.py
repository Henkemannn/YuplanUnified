from __future__ import annotations

from core.planera_v2.comparison import (
    build_day_comparison_report,
    compare_current_planera_vs_v2_day,
)
from core.planera_v2.dev_runner import PlaneraV2DevRun
from core.planera_v2.domain import PlanResult, PlanRequest, Totals


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


def test_comparison_matching_case_for_totals_units_and_effective_deviations() -> None:
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
            },
            {
                "department_id": "unit_b",
                "meals": {
                    "lunch": {
                        "residents_total": 8,
                        "special_diets": [
                            {"diet_type_id": "not_fri", "count": 3},
                        ],
                    }
                },
            },
        ]
    }

    comparison = compare_current_planera_vs_v2_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A"), ("unit_b", "Unit B")],
    )

    assert all(comparison.matches.values())
    assert comparison.mismatches == []


def test_comparison_mismatch_case_reports_notes() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 12,
                        "special_diets": [
                            {"diet_type_id": "ej_fisk", "count": 2},
                        ],
                    }
                },
            }
        ]
    }

    def _fake_dev_runner(**kwargs: object) -> PlaneraV2DevRun:
        return PlaneraV2DevRun(
            request=PlanRequest(baseline=99, context={"site_id": "site_1", "date": "2026-04-14", "meal_key": "lunch"}),
            result=PlanResult(
                totals=Totals(baseline_total=99, deviation_total=0, normal_total=99),
                per_form={},
                per_combination={},
                per_unit={},
                per_unit_breakdown={},
                warnings=[],
            ),
            formatted_debug="Totals:\n",
            formatted_clean="Plan Result\n",
            formatted_kitchen="TOTAL\n",
        )

    comparison = compare_current_planera_vs_v2_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
        dev_runner=_fake_dev_runner,
    )

    assert not comparison.matches["total_baseline"]
    assert comparison.mismatches


def test_comparison_report_contains_sections_and_caveats() -> None:
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

    comparison = compare_current_planera_vs_v2_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-16",
        meal_key="dessert",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )
    report = build_day_comparison_report(comparison)

    assert "Current Planera 1.0 Summary" in report
    assert "Planera 2.0 Summary" in report
    assert "Match / Mismatch" in report
    assert "Caveats" in report
    assert "Form semantics are currently adapter fallback labels" in report
    assert "Comparison is strongest on totals, unit baselines, and effective unit deviations." in report
