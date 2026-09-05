from __future__ import annotations

import uuid

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import (
    DepartmentRequirementGroupServiceOverridesRepo,
)
from core.planera_v2.comparison import compare_current_legacy_and_canonical_v2_day_from_payload
from core.planera_v2.dev_runner import run_planera_v2_from_canonical_requirement_groups


def _seed_department(site_id: str, name: str, baseline_total: int) -> dict:
    department, _ = DepartmentsRepo().create_department(
        site_id=site_id,
        name=name,
        resident_count_mode="fixed",
        resident_count_fixed=baseline_total,
    )
    return department


def _seed_atomic_requirement(site_id: str, name: str, requirement_key: str) -> int:
    return DietTypesRepo().create(
        site_id=site_id,
        name=name,
        default_select=False,
        semantics="atomic",
        requirement_key=requirement_key,
    )


def _create_group(department_id: str, requirement_ids: list[int], *, quantity: int, label: str) -> str:
    group = DepartmentRequirementGroupsRepo().create_group(department_id, quantity, requirement_ids, label=label)
    return str(group["id"])


def _current_payload(site_id: str, departments: list[dict[str, object]]) -> dict[str, object]:
    return {
        "site_id": site_id,
        "departments": departments,
    }


def test_realistic_kommun_multi_unit_canonical_day_acceptance(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Kommun acceptance site {uuid.uuid4()}")

        dept_a = _seed_department(site["id"], "Department A", 10)
        dept_b = _seed_department(site["id"], "Department B", 8)
        dept_c = _seed_department(site["id"], "Department C", 12)

        req_a_key = f"req_a_{uuid.uuid4().hex[:8]}"
        req_ab_1_key = f"req_ab_1_{uuid.uuid4().hex[:8]}"
        req_ab_2_key = f"req_ab_2_{uuid.uuid4().hex[:8]}"
        req_c_key = f"req_c_{uuid.uuid4().hex[:8]}"

        req_a_id = _seed_atomic_requirement(site["id"], "Requirement A", req_a_key)
        req_ab_1_id = _seed_atomic_requirement(site["id"], "Requirement AB 1", req_ab_1_key)
        req_ab_2_id = _seed_atomic_requirement(site["id"], "Requirement AB 2", req_ab_2_key)
        req_c_id = _seed_atomic_requirement(site["id"], "Requirement C", req_c_key)

        group_a_id = _create_group(dept_a["id"], [req_a_id], quantity=2, label="Group A")
        group_ab_id = _create_group(dept_a["id"], [req_ab_1_id, req_ab_2_id], quantity=1, label="Group AB")
        group_c_id = _create_group(dept_b["id"], [req_c_id], quantity=1, label="Group C")

        DepartmentRequirementGroupServiceOverridesRepo().set_override(group_c_id, "2026-09-08", "lunch", 3)

        day_payload = _current_payload(
            site["id"],
            [
                {
                    "department_id": dept_a["id"],
                    "department_name": dept_a["name"],
                    "meals": {
                        "lunch": {
                            "residents_total": 10,
                            "special_diets": [
                                {"diet_type_id": "legacy_deviation_a", "count": 3},
                            ],
                        }
                    },
                },
                {
                    "department_id": dept_b["id"],
                    "department_name": dept_b["name"],
                    "meals": {
                        "lunch": {
                            "residents_total": 8,
                            "special_diets": [
                                {"diet_type_id": "legacy_deviation_b", "count": 3},
                            ],
                        }
                    },
                },
                {
                    "department_id": dept_c["id"],
                    "department_name": dept_c["name"],
                    "meals": {
                        "lunch": {
                            "residents_total": 12,
                            "special_diets": [],
                        }
                    },
                },
            ],
        )

        three_way = compare_current_legacy_and_canonical_v2_day_from_payload(
            day_payload,
            tenant_id=1,
            site_id=site["id"],
            iso_date="2026-09-08",
            meal_key="lunch",
            expected_unit_ids=[dept_a["id"], dept_b["id"], dept_c["id"]],
        )

        canonical_run = run_planera_v2_from_canonical_requirement_groups(
            site_id=site["id"],
            service_date="2026-09-08",
            meal_key="lunch",
            unit_baselines={
                dept_a["id"]: 10,
                dept_b["id"]: 8,
                dept_c["id"]: 12,
            },
        )

        assert three_way.legacy.parity_verdict == "PASS"
        assert three_way.legacy.compatibility_verdict == "NOT_PROVABLE"
        assert three_way.canonical.baseline_parity_verdict == "PASS"
        assert three_way.canonical.numerical_parity_verdict == "PASS"
        assert three_way.canonical.representation_verdict == "NOT_COMPARABLE"
        assert three_way.canonical.compatibility_verdict == "PASS"
        assert three_way.canonical.production_acceptance_verdict == "PASS"

        canonical = three_way.canonical.canonical_v2
        assert canonical.unit_baselines == {
            dept_a["id"]: 10,
            dept_b["id"]: 8,
            dept_c["id"]: 12,
        }
        assert canonical.unit_deviation_totals == {
            dept_a["id"]: 3,
            dept_b["id"]: 3,
            dept_c["id"]: 0,
        }
        assert canonical.unit_normal_totals == {
            dept_a["id"]: 7,
            dept_b["id"]: 5,
            dept_c["id"]: 12,
        }
        assert canonical.totals == {
            "baseline_total": 30,
            "deviation_total": 6,
            "normal_total": 24,
        }

        assert canonical_run.result.totals.baseline_total == 30
        assert canonical_run.result.totals.deviation_total == 6
        assert canonical_run.result.totals.normal_total == 24
        assert canonical_run.request.context["source"] == "canonical_requirement_groups"
        assert canonical_run.request.context["compatibility_source_precision"] == "canonical_atomic_groups"
        assert canonical_run.request.context["compatibility_status"] == "resolved"

        refs = canonical_run.request.context["requirement_group_refs"]
        assert len(refs) == 3
        refs_by_group = {ref["group_id"]: ref for ref in refs}
        assert refs_by_group[group_a_id]["quantity"] == 2
        assert len(refs_by_group[group_a_id]["category_keys"]) == 1
        assert refs_by_group[group_ab_id]["quantity"] == 1
        assert len(refs_by_group[group_ab_id]["category_keys"]) == 2
        assert refs_by_group[group_c_id]["quantity"] == 3
        assert len(refs_by_group[group_c_id]["category_keys"]) == 1
        assert len({ref["group_id"] for ref in refs}) == 3
        assert all(ref["quantity"] > 0 for ref in refs)
        assert {ref["unit_id"] for ref in refs} == {dept_a["id"], dept_b["id"]}
        assert dept_c["id"] not in {ref["unit_id"] for ref in refs}

        for unit_id, baseline_total, deviation_total, normal_total in (
            (dept_a["id"], 10, 3, 7),
            (dept_b["id"], 8, 3, 5),
            (dept_c["id"], 12, 0, 12),
        ):
            assert normal_total + deviation_total == baseline_total
            assert canonical.unit_baselines[unit_id] == baseline_total
            assert canonical.unit_deviation_totals[unit_id] == deviation_total
            assert canonical.unit_normal_totals[unit_id] == normal_total

        assert canonical.totals["normal_total"] + canonical.totals["deviation_total"] == canonical.totals["baseline_total"]