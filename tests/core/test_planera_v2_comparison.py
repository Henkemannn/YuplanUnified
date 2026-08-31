from __future__ import annotations

import os

from sqlalchemy import text

from core.planera_v2.comparison import (
    build_day_comparison_report,
    compare_current_planera_vs_v2_day,
    compare_current_planera_vs_v2_day_from_payload,
)
from core.planera_v2.dev_runner import PlaneraV2DevRun
from core.planera_v2.domain import Deviation, PlanResult, PlanRequest, Totals, UnitInput
from core.db import get_session


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
    assert comparison.parity_verdict == "PASS"
    assert comparison.compatibility_verdict == "PASS"


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
    assert comparison.parity_verdict == "FAIL"


def test_comparison_reports_not_provable_when_shadow_input_is_ambiguous() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 10,
                        "special_diets": [],
                    }
                },
            }
        ]
    }

    def _fake_dev_runner(**kwargs: object) -> PlaneraV2DevRun:
        return PlaneraV2DevRun(
            request=PlanRequest(
                baseline=10,
                units=[UnitInput(unit_id="unit_a", baseline_total=10)],
                context={
                    "site_id": "site_1",
                    "date": "2026-04-14",
                    "meal_key": "lunch",
                    "compatibility_status": "ambiguous",
                    "compatibility_warnings": ["aggregate-only source data cannot prove recipient-level compatibility"],
                },
            ),
            result=PlanResult(
                totals=Totals(baseline_total=10, deviation_total=0, normal_total=10),
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

    report = build_day_comparison_report(comparison)

    assert comparison.parity_verdict == "PASS"
    assert comparison.compatibility_verdict == "NOT_PROVABLE"
    assert comparison.compatibility_notes
    assert "Compatibility verdict: NOT_PROVABLE" in report
    assert "aggregate-only source data cannot prove recipient-level compatibility" in report


def test_comparison_is_deterministic_for_same_input() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 3,
                        "special_diets": [
                            {"diet_type_id": "laktos och gluten", "count": 1},
                        ],
                    }
                },
            }
        ]
    }

    comparison_a = compare_current_planera_vs_v2_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )
    comparison_b = compare_current_planera_vs_v2_day(
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        planera_service=_FakePlaneraService(payload),
        departments=[("unit_a", "Unit A")],
    )

    assert comparison_a == comparison_b


def test_comparison_preserves_deterministic_combination_identity() -> None:
    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "meals": {
                    "lunch": {
                        "residents_total": 1,
                        "special_diets": [
                            {"diet_type_id": "marker_a__marker_b", "count": 1},
                        ],
                    }
                },
            }
        ]
    }

    def _fake_dev_runner(**kwargs: object) -> PlaneraV2DevRun:
        return PlaneraV2DevRun(
            request=PlanRequest(
                baseline=1,
                units=[],
                deviations=[
                    Deviation(
                        form="texture_soft",
                        category_keys=["marker_b", "marker_a"],
                        quantity=1,
                        unit_id="unit_a",
                    )
                ],
                context={"site_id": "site_1", "date": "2026-04-14", "meal_key": "lunch"},
            ),
            result=PlanResult(
                totals=Totals(baseline_total=1, deviation_total=1, normal_total=0),
                per_form={"texture_soft": 1},
                per_combination={"texture_soft__marker_a__marker_b": 1},
                per_unit={"unit_a": 1},
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

    assert comparison.v2.unit_special_deviations == {"unit_a": {"marker_a__marker_b": 1}}
    assert comparison.matches["unit_special_deviations"]


def test_comparison_read_only_does_not_mutate_weekview_or_registration_state(app_session) -> None:
    app = app_session
    with app.app_context():
        os.environ["YP_ENABLE_SQLITE_BOOTSTRAP"] = "1"
        from core.db import create_all

        create_all()

        db = get_session()
        try:
            before_weekview_versions_exists = db.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='weekview_versions'")
            ).scalar_one()
            before_registrations_exists = db.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='weekview_registrations'")
            ).scalar_one()
            before_weekview_versions = (
                db.execute(text("SELECT COUNT(*) FROM weekview_versions")).scalar_one() if before_weekview_versions_exists else 0
            )
            before_registrations = (
                db.execute(text("SELECT COUNT(*) FROM weekview_registrations")).scalar_one() if before_registrations_exists else 0
            )
        finally:
            db.close()

    payload = {
        "departments": [
            {
                "department_id": "unit_a",
                "department_name": "Parity Dept",
                "meals": {
                    "lunch": {
                        "residents_total": 5,
                        "special_diets": [],
                    }
                },
            }
        ]
    }

    comparison = compare_current_planera_vs_v2_day_from_payload(
        payload,
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
    )

    assert comparison.parity_verdict in {"PASS", "FAIL"}

    with app.app_context():
        db = get_session()
        try:
            after_weekview_versions_exists = db.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='weekview_versions'")
            ).scalar_one()
            after_registrations_exists = db.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='weekview_registrations'")
            ).scalar_one()
            after_weekview_versions = (
                db.execute(text("SELECT COUNT(*) FROM weekview_versions")).scalar_one() if after_weekview_versions_exists else 0
            )
            after_registrations = (
                db.execute(text("SELECT COUNT(*) FROM weekview_registrations")).scalar_one() if after_registrations_exists else 0
            )
        finally:
            db.close()

    assert before_weekview_versions == after_weekview_versions
    assert before_registrations == after_registrations


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
    assert "Comparison is strongest on totals, unit baselines, and effective unit deviations." in report
    assert "Parity verdict: PASS" in report
    assert "Compatibility verdict:" in report
