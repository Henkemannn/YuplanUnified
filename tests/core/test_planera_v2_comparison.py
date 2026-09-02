from __future__ import annotations

import os
import uuid

from sqlalchemy import text

from core.planera_v2.comparison import (
    CanonicalPlaneraComparison,
    build_day_comparison_report,
    compare_current_legacy_and_canonical_v2_day_from_payload,
    compare_current_planera_vs_v2_day,
    compare_current_planera_vs_v2_day_from_payload,
)
from core.planera_v2.dev_runner import PlaneraV2DevRun, run_planera_v2_from_canonical_requirement_groups
from core.planera_v2.domain import Deviation, PlanResult, PlanRequest, Totals, UnitInput
from core.db import get_session
from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import (
    DepartmentRequirementGroupServiceOverridesRepo,
)


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


def _current_payload_for(meal_key: str, rows: list[tuple[str, int, int]]) -> dict[str, object]:
    departments: list[dict[str, object]] = []
    for unit_id, baseline_total, deviation_total in rows:
        special_diets: list[dict[str, object]] = []
        if deviation_total > 0:
            special_diets.append({"diet_type_id": f"legacy_{unit_id}", "count": deviation_total})
        departments.append(
            {
                "department_id": unit_id,
                "meals": {
                    meal_key: {
                        "residents_total": baseline_total,
                        "special_diets": special_diets,
                    }
                },
            }
        )
    return {"departments": departments}


def _seed_canonical_department(site_id: str, name: str) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    return department


def _seed_canonical_group(
    site_id: str,
    department_id: str,
    requirement_count: int,
    *,
    quantity: int,
    label: str,
    active: bool = True,
    override_quantity: int | None = None,
    service_date: str = "2026-09-08",
    meal_key: str = "lunch",
) -> str:
    requirement_ids = [
        DietTypesRepo().create(
            site_id=site_id,
            name=f"Requirement {uuid.uuid4().hex[:8]}",
            default_select=False,
            semantics="atomic",
        )
        for _ in range(requirement_count)
    ]
    group = DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)
    if not active:
        DepartmentRequirementGroupsRepo().update_group(group["id"], is_active=False)
    if override_quantity is not None:
        DepartmentRequirementGroupServiceOverridesRepo().set_override(group["id"], service_date, meal_key, override_quantity)
    return str(group["id"])


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
    assert comparison.compatibility_verdict == "NOT_PROVABLE"


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


def test_comparison_reports_not_provable_for_legacy_aggregate_source() -> None:
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

    comparison = compare_current_planera_vs_v2_day_from_payload(
        payload,
        tenant_id=1,
        site_id="site_1",
        iso_date="2026-04-14",
        meal_key="lunch",
        departments=[("unit_a", "Unit A")],
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
    assert "Compatibility verdict: NOT_PROVABLE" in report


def test_three_way_standard_only_keeps_legacy_shadow_unchanged(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Standard only site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        payload = _current_payload_for("lunch", [(department["id"], 10, 0)])
        three_way = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )

    assert isinstance(three_way.canonical, CanonicalPlaneraComparison)
    assert three_way.legacy.parity_verdict == "PASS"
    assert three_way.legacy.compatibility_verdict == "NOT_PROVABLE"
    assert three_way.canonical.baseline_parity_verdict == "PASS"
    assert three_way.canonical.numerical_parity_verdict == "PASS"
    assert three_way.canonical.representation_verdict == "PASS"
    assert three_way.canonical.compatibility_verdict == "PASS"
    assert three_way.canonical.context["tenant_id"] == "1"


def test_three_way_atomic_and_combined_representation_rules(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical comparison site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        _seed_canonical_group(site["id"], department["id"], 1, quantity=2, label="Atomic A")

        payload = _current_payload_for("lunch", [(department["id"], 10, 2)])
        three_way_atomic = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )

        assert three_way_atomic.canonical.baseline_parity_verdict == "PASS"
        assert three_way_atomic.canonical.numerical_parity_verdict == "PASS"
        assert three_way_atomic.canonical.representation_verdict == "NOT_COMPARABLE"
        assert three_way_atomic.canonical.compatibility_verdict == "PASS"
        assert three_way_atomic.canonical.context["tenant_id"] == "1"

        site_two = SitesRepo().create_site(f"Canonical combined site {uuid.uuid4()}")[0]
        department_two = _seed_canonical_department(site_two["id"], "Unit B")
        combined_group = _seed_canonical_group(site_two["id"], department_two["id"], 2, quantity=1, label="Combined AB")

        combined_payload = _current_payload_for("lunch", [(department_two["id"], 10, 1)])
        three_way_combined = compare_current_legacy_and_canonical_v2_day_from_payload(
            combined_payload,
            tenant_id=1,
            site_id=site_two["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )

        assert three_way_combined.canonical.numerical_parity_verdict == "PASS"
        assert three_way_combined.canonical.representation_verdict == "NOT_COMPARABLE"
        assert three_way_combined.canonical.compatibility_verdict == "PASS"
        canonical_run = run_planera_v2_from_canonical_requirement_groups(
            site_id=site_two["id"],
            service_date="2026-04-14",
            meal_key="lunch",
            unit_baselines={department_two["id"]: 10},
        )
        assert canonical_run.result.totals.deviation_total == 1
        assert canonical_run.result.totals.normal_total == 9
        assert len(canonical_run.request.context["requirement_group_refs"]) == 1
        assert canonical_run.request.context["requirement_group_refs"][0]["group_id"] == combined_group


def test_three_way_numerical_parity_matches_and_swapped_units_fail(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical numerical site {uuid.uuid4()}")[0]
        dept_a = _seed_canonical_department(site["id"], "Unit A")
        dept_b = _seed_canonical_department(site["id"], "Unit B")
        _seed_canonical_group(site["id"], dept_a["id"], 1, quantity=3, label="Group A")
        _seed_canonical_group(site["id"], dept_b["id"], 1, quantity=1, label="Group B")

        correct_payload = _current_payload_for("lunch", [(dept_a["id"], 10, 3), (dept_b["id"], 20, 1)])
        three_way_correct = compare_current_legacy_and_canonical_v2_day_from_payload(
            correct_payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )
        assert three_way_correct.canonical.baseline_parity_verdict == "PASS"
        assert three_way_correct.canonical.numerical_parity_verdict == "PASS"
        assert three_way_correct.canonical.context["tenant_id"] == "1"
        assert three_way_correct.canonical.canonical_v2.unit_deviation_totals == {dept_a["id"]: 3, dept_b["id"]: 1}

        swapped_site = SitesRepo().create_site(f"Canonical swapped site {uuid.uuid4()}")[0]
        swapped_a = _seed_canonical_department(swapped_site["id"], "Unit A")
        swapped_b = _seed_canonical_department(swapped_site["id"], "Unit B")
        _seed_canonical_group(swapped_site["id"], swapped_a["id"], 1, quantity=1, label="Swapped A")
        _seed_canonical_group(swapped_site["id"], swapped_b["id"], 1, quantity=3, label="Swapped B")

        swapped_payload = _current_payload_for("lunch", [(swapped_a["id"], 10, 3), (swapped_b["id"], 20, 1)])
        three_way_swapped = compare_current_legacy_and_canonical_v2_day_from_payload(
            swapped_payload,
            tenant_id=1,
            site_id=swapped_site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )

        assert three_way_swapped.canonical.baseline_parity_verdict == "PASS"
        assert three_way_swapped.canonical.numerical_parity_verdict == "FAIL"
        assert any("Per-unit deviation totals differ." in note for note in three_way_swapped.canonical.notes)


def test_three_way_override_and_state_rules(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical override site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        group_id = _seed_canonical_group(site["id"], department["id"], 1, quantity=2, label="Group A")

        match_payload = _current_payload_for("lunch", [(department["id"], 10, 4)])
        DepartmentRequirementGroupServiceOverridesRepo().set_override(group_id, "2026-04-14", "lunch", 4)
        three_way_match = compare_current_legacy_and_canonical_v2_day_from_payload(
            match_payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )
        assert three_way_match.canonical.numerical_parity_verdict == "PASS"
        assert three_way_match.canonical.context["tenant_id"] == "1"
        assert any(
            "Legacy bucket labels and canonical atomic requirement keys are not comparable by string identity."
            in note
            for note in three_way_match.canonical.notes
        )

        mismatch_payload = _current_payload_for("lunch", [(department["id"], 10, 2)])
        three_way_mismatch = compare_current_legacy_and_canonical_v2_day_from_payload(
            mismatch_payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )
        assert three_way_mismatch.canonical.baseline_parity_verdict == "PASS"
        assert three_way_mismatch.canonical.numerical_parity_verdict == "FAIL"
        assert three_way_mismatch.canonical.compatibility_verdict == "PASS"

        zero_group_site = SitesRepo().create_site(f"Canonical zero site {uuid.uuid4()}")[0]
        zero_department = _seed_canonical_department(zero_group_site["id"], "Unit Zero")
        zero_group = _seed_canonical_group(zero_group_site["id"], zero_department["id"], 1, quantity=2, label="Zero Group")
        DepartmentRequirementGroupServiceOverridesRepo().set_override(zero_group, "2026-04-14", "lunch", 0)
        zero_payload = _current_payload_for("lunch", [(zero_department["id"], 10, 0)])
        three_way_zero = compare_current_legacy_and_canonical_v2_day_from_payload(
            zero_payload,
            tenant_id=1,
            site_id=zero_group_site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )
        assert three_way_zero.canonical.numerical_parity_verdict == "PASS"

        inactive_site = SitesRepo().create_site(f"Canonical inactive site {uuid.uuid4()}")[0]
        inactive_department = _seed_canonical_department(inactive_site["id"], "Unit Inactive")
        inactive_group = _seed_canonical_group(
            inactive_site["id"],
            inactive_department["id"],
            1,
            quantity=2,
            label="Inactive Group",
            active=False,
            override_quantity=7,
        )
        inactive_payload = _current_payload_for("lunch", [(inactive_department["id"], 10, 0)])
        three_way_inactive = compare_current_legacy_and_canonical_v2_day_from_payload(
            inactive_payload,
            tenant_id=1,
            site_id=inactive_site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )
        assert three_way_inactive.canonical.numerical_parity_verdict == "PASS"


def test_three_way_baseline_mismatch_meal_normalization_and_determinism(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical baseline site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        payload = _current_payload_for("evening", [(department["id"], 10, 0)])
        three_way_a = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="EVENING",
        )
        three_way_b = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="EVENING",
        )

        assert three_way_a.canonical.context["meal_key"] == "evening"
        assert three_way_a == three_way_b

        def _fake_canonical_runner(**kwargs: object) -> object:
            from core.planera_v2.dev_runner import PlaneraV2DevRun
            from core.planera_v2.domain import PlanRequest, PlanResult, Totals, UnitInput

            unit_id = department["id"]
            return PlaneraV2DevRun(
                request=PlanRequest(
                    baseline=12,
                    units=[UnitInput(unit_id=unit_id, baseline_total=12)],
                    deviations=[],
                    context={"site_id": site["id"], "date": "2026-04-14", "meal_key": "evening", "tenant_id": "1", "compatibility_source_precision": "canonical_atomic_groups", "compatibility_status": "resolved"},
                ),
                result=PlanResult(totals=Totals(baseline_total=12, deviation_total=0, normal_total=12), per_form={}, per_combination={}, per_unit={}, per_unit_breakdown={}, warnings=[]),
                formatted_debug="",
                formatted_clean="",
                formatted_kitchen="",
            )

        mismatch = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="EVENING",
            canonical_runner=_fake_canonical_runner,
        )
        assert mismatch.canonical.baseline_parity_verdict == "FAIL"

        lunch_payload = _current_payload_for("lunch", [(department["id"], 10, 0)])
        lunch_three_way = compare_current_legacy_and_canonical_v2_day_from_payload(
            lunch_payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key=" Lunch ",
        )
        assert lunch_three_way.canonical.context["meal_key"] == "lunch"


def test_two_groups_same_department_produce_two_group_refs_and_numerical_pass(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical two group site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        group_1 = _seed_canonical_group(site["id"], department["id"], 1, quantity=1, label="G1")
        group_2 = _seed_canonical_group(site["id"], department["id"], 1, quantity=2, label="G2")
        payload = _current_payload_for("lunch", [(department["id"], 10, 3)])

        three_way = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )

        assert three_way.canonical.numerical_parity_verdict == "PASS"
        assert three_way.canonical.canonical_v2.unit_deviation_totals[department["id"]] == 3
        assert three_way.canonical.canonical_v2.unit_normal_totals[department["id"]] == 7
        canonical_run = run_planera_v2_from_canonical_requirement_groups(
            site_id=site["id"],
            service_date="2026-04-14",
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        assert len(canonical_run.request.context["requirement_group_refs"]) == 2
        assert {ref["group_id"] for ref in canonical_run.request.context["requirement_group_refs"]} == {group_1, group_2}


def test_multi_key_canonical_group_counts_as_three_not_six(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical multi-key site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        _seed_canonical_group(site["id"], department["id"], 2, quantity=3, label="A+B")
        payload = _current_payload_for("lunch", [(department["id"], 10, 3)])

        three_way = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )

        assert three_way.canonical.canonical_v2.unit_deviation_totals[department["id"]] == 3
        assert three_way.canonical.canonical_v2.unit_normal_totals[department["id"]] == 7
        assert three_way.canonical.canonical_v2.totals["deviation_total"] == 3
        assert three_way.canonical.canonical_v2.totals["normal_total"] == 7
        assert three_way.canonical.baseline_parity_verdict == "PASS"
        assert three_way.canonical.numerical_parity_verdict == "PASS"
        assert three_way.canonical.representation_verdict == "NOT_COMPARABLE"
        assert three_way.canonical.compatibility_verdict == "PASS"


def test_total_normal_mismatch_forces_numerical_fail(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical total normal site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        _seed_canonical_group(site["id"], department["id"], 1, quantity=3, label="Group A")
        payload = _current_payload_for("lunch", [(department["id"], 10, 3)])

        def _fake_canonical_runner(**kwargs: object):
            from core.planera_v2.dev_runner import PlaneraV2DevRun
            from core.planera_v2.domain import PlanRequest, PlanResult, Totals, UnitInput

            unit_id = str(kwargs["unit_baselines"].keys().__iter__().__next__())
            return PlaneraV2DevRun(
                request=PlanRequest(
                    baseline=10,
                    units=[UnitInput(unit_id=unit_id, baseline_total=10)],
                    deviations=[],
                    context={"site_id": site["id"], "date": "2026-04-14", "meal_key": "lunch", "tenant_id": "1", "compatibility_source_precision": "canonical_atomic_groups", "compatibility_status": "resolved"},
                ),
                result=PlanResult(totals=Totals(baseline_total=10, deviation_total=3, normal_total=6), per_form={}, per_combination={}, per_unit={}, per_unit_breakdown={}, warnings=[]),
                formatted_debug="",
                formatted_clean="",
                formatted_kitchen="",
            )

        three_way = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
            canonical_runner=_fake_canonical_runner,
        )

        assert three_way.canonical.matches["total_normal"] is False
        assert three_way.canonical.numerical_parity_verdict == "FAIL"


def test_canonical_deviation_exceeds_baseline_preserves_warning_notes(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical warning site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        _seed_canonical_group(site["id"], department["id"], 1, quantity=2, label="Group A")
        payload = _current_payload_for("lunch", [(department["id"], 1, 2)])

        three_way = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
        )

        assert three_way.canonical.baseline_parity_verdict == "PASS"
        assert three_way.canonical.numerical_parity_verdict == "PASS"
        assert three_way.canonical.compatibility_verdict == "PASS"
        assert any("canonical deviations exceed baseline" in note for note in three_way.canonical.notes)


def test_baseline_mismatch_uses_fake_canonical_runner_without_override_argument(app_session) -> None:
    with app_session.app_context():
        site = SitesRepo().create_site(f"Canonical baseline mismatch site {uuid.uuid4()}")[0]
        department = _seed_canonical_department(site["id"], "Unit A")
        payload = _current_payload_for("lunch", [(department["id"], 10, 0)])

        def _fake_canonical_runner(**kwargs: object):
            from core.planera_v2.dev_runner import PlaneraV2DevRun
            from core.planera_v2.domain import PlanRequest, PlanResult, Totals, UnitInput

            unit_id = str(kwargs["unit_baselines"].keys().__iter__().__next__())
            return PlaneraV2DevRun(
                request=PlanRequest(
                    baseline=12,
                    units=[UnitInput(unit_id=unit_id, baseline_total=12)],
                    deviations=[],
                    context={"site_id": site["id"], "date": "2026-04-14", "meal_key": "lunch", "tenant_id": "1", "compatibility_source_precision": "canonical_atomic_groups", "compatibility_status": "resolved"},
                ),
                result=PlanResult(totals=Totals(baseline_total=12, deviation_total=0, normal_total=12), per_form={}, per_combination={}, per_unit={}, per_unit_breakdown={}, warnings=[]),
                formatted_debug="",
                formatted_clean="",
                formatted_kitchen="",
            )

        mismatch = compare_current_legacy_and_canonical_v2_day_from_payload(
            payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-04-14",
            meal_key="lunch",
            canonical_runner=_fake_canonical_runner,
        )

        assert mismatch.canonical.baseline_parity_verdict == "FAIL"
