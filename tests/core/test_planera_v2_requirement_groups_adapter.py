from __future__ import annotations

from datetime import date
import uuid

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import (
    DepartmentRequirementGroupServiceOverridesRepo,
)
from core.planera_v2.adapters.kommun_from_requirement_groups import (
    build_planning_slice_from_requirement_groups,
)
from core.planera_v2.engine import compute_plan


def _seed_department(site_id: str, name: str | None = None) -> dict:
    dept_repo = DepartmentsRepo()
    department, _ = dept_repo.create_department(
        site_id=site_id,
        name=name or f"Department {uuid.uuid4()}",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    return department


def _seed_requirement_with_key(site_id: str, name: str, requirement_key: str) -> int:
    from core.db import get_session

    conn = get_session()
    try:
        conn.execute(
            text(
                "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, :name, 'Övrigt', :requirement_key, 'atomic', 0)"
            ),
            {"site_id": site_id, "name": name, "requirement_key": requirement_key},
        )
        conn.commit()
        row = conn.execute(
                text("SELECT id FROM dietary_types WHERE requirement_key=:requirement_key AND site_id=:site_id"),
                {"requirement_key": requirement_key, "site_id": site_id},
        ).fetchone()
        assert row is not None
        return int(row[0])
    finally:
        conn.close()


def _create_group(site_id: str, department_id: str, requirement_ids: list[int], *, quantity: int, label: str) -> str:
    repo = DepartmentRequirementGroupsRepo()
    group = repo.create_group(department_id, quantity, requirement_ids, label=label)
    return str(group["id"])


def test_single_atomic_group_maps_to_one_deviation_and_requirement_key(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E site {uuid.uuid4()}")
        department = _seed_department(site["id"], "Unit A")
        gluten_key = f"req_gluten_{uuid.uuid4().hex[:8]}"
        requirement_id = _seed_requirement_with_key(site["id"], "Gluten", gluten_key)
        _create_group(site["id"], department["id"], [requirement_id], quantity=1, label="Group A")

        slice_ = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )

        assert slice_.baseline == 10
        assert [unit.unit_id for unit in slice_.units] == [department["id"]]
        assert len(slice_.deviations) == 1
        deviation = slice_.deviations[0]
        assert deviation.form == "unspecified"
        assert deviation.category_keys == [gluten_key]
        assert deviation.quantity == 1
        assert deviation.unit_id == department["id"]
        assert slice_.context["source"] == "canonical_requirement_groups"
        assert slice_.context["compatibility_source_precision"] == "canonical_atomic_groups"
        assert slice_.context["compatibility_status"] == "resolved"


def test_multi_requirement_group_preserves_quantity_and_conserves_plan_total(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E multi site {uuid.uuid4()}")
        department = _seed_department(site["id"], "Unit A")
        gluten_key = f"req_gluten_{uuid.uuid4().hex[:8]}"
        lactose_key = f"req_lactose_{uuid.uuid4().hex[:8]}"
        req_a = _seed_requirement_with_key(site["id"], "Gluten", gluten_key)
        req_b = _seed_requirement_with_key(site["id"], "Lactose", lactose_key)
        _create_group(site["id"], department["id"], [req_a, req_b], quantity=3, label="Group AB")

        slice_ = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date="2026-09-08",
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        result = compute_plan(slice_.to_plan_request())

        assert len(slice_.deviations) == 1
        assert slice_.deviations[0].category_keys == [gluten_key, lactose_key]
        assert slice_.deviations[0].quantity == 3
        assert result.totals.baseline_total == 10
        assert result.totals.deviation_total == 3
        assert result.totals.normal_total == 7


def test_service_override_zero_inactive_reactivate_and_date_meal_isolation(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E override site {uuid.uuid4()}")
        department = _seed_department(site["id"], "Unit A")
        gluten_key = f"req_gluten_{uuid.uuid4().hex[:8]}"
        requirement_id = _seed_requirement_with_key(site["id"], "Gluten", gluten_key)
        group_id = _create_group(site["id"], department["id"], [requirement_id], quantity=2, label="Group A")
        overrides = DepartmentRequirementGroupServiceOverridesRepo()

        slice_default = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        assert slice_default.deviations[0].quantity == 2
        assert overrides.resolve_effective_quantity(group_id, date(2026, 9, 8), "lunch") == 2

        overrides.set_override(group_id, date(2026, 9, 8), "lunch", 4)
        slice_override = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        assert slice_override.deviations[0].quantity == 4
        assert overrides.resolve_effective_quantity(group_id, date(2026, 9, 8), "lunch") == 4

        slice_other_meal = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="dinner",
            unit_baselines={department["id"]: 10},
        )
        assert slice_other_meal.deviations[0].quantity == 2
        assert overrides.resolve_effective_quantity(group_id, date(2026, 9, 8), "dinner") == 2

        slice_other_date = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 9),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        assert slice_other_date.deviations[0].quantity == 2
        assert overrides.resolve_effective_quantity(group_id, date(2026, 9, 9), "lunch") == 2

        overrides.set_override(group_id, date(2026, 9, 8), "lunch", 0)
        slice_zero = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        assert slice_zero.deviations == ()
        assert overrides.resolve_effective_quantity(group_id, date(2026, 9, 8), "lunch") == 0

        overrides.set_override(group_id, date(2026, 9, 8), "lunch", 7)
        from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo

        DepartmentRequirementGroupsRepo().update_group(group_id, is_active=False)
        slice_inactive = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        assert slice_inactive.deviations == ()
        assert overrides.resolve_effective_quantity(group_id, date(2026, 9, 8), "lunch") == 0

        DepartmentRequirementGroupsRepo().update_group(group_id, is_active=True)
        slice_reactivated = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
        )
        assert slice_reactivated.deviations[0].quantity == 7
        assert overrides.resolve_effective_quantity(group_id, date(2026, 9, 8), "lunch") == 7


def test_canonical_context_spoof_protection(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E spoof site {uuid.uuid4()}")
        department = _seed_department(site["id"], "Unit A")
        gluten_key = f"req_gluten_{uuid.uuid4().hex[:8]}"
        requirement_id = _seed_requirement_with_key(site["id"], "Gluten", gluten_key)
        group_id = _create_group(site["id"], department["id"], [requirement_id], quantity=1, label="Group A")

        slice_ = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 10},
            context={
                "source": "spoofed",
                "site_id": "spoofed",
                "date": "spoofed",
                "meal_key": "spoofed",
                "compatibility_source_precision": "spoofed",
                "compatibility_status": "spoofed",
                "requirement_group_refs": ["spoofed"],
                "compatibility_warnings": ["spoofed"],
                "caller_key": "keep-me",
            },
        )

        assert slice_.context["source"] == "canonical_requirement_groups"
        assert slice_.context["site_id"] == site["id"]
        assert slice_.context["date"] == "2026-09-08"
        assert slice_.context["meal_key"] == "lunch"
        assert slice_.context["compatibility_source_precision"] == "canonical_atomic_groups"
        assert slice_.context["compatibility_status"] == "resolved"
        assert slice_.context["requirement_group_refs"] == [
            {
                "group_id": group_id,
                "unit_id": department["id"],
                "category_keys": [gluten_key],
                "quantity": 1,
            }
        ]
        assert "compatibility_warnings" not in slice_.context
        assert slice_.context["caller_key"] == "keep-me"


def test_two_groups_two_units_deterministic_refs_and_context(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E deterministic site {uuid.uuid4()}")
        dept_a = _seed_department(site["id"])
        dept_b = _seed_department(site["id"])
        gluten_key = f"req_gluten_{uuid.uuid4().hex[:8]}"
        lactose_key = f"req_lactose_{uuid.uuid4().hex[:8]}"
        fish_key = f"req_fish_{uuid.uuid4().hex[:8]}"
        req_a = _seed_requirement_with_key(site["id"], "Gluten", gluten_key)
        req_b = _seed_requirement_with_key(site["id"], "Lactose", lactose_key)
        req_c = _seed_requirement_with_key(site["id"], "Fish", fish_key)
        group1 = _create_group(site["id"], dept_a["id"], [req_a, req_b], quantity=1, label="G1")
        group2 = _create_group(site["id"], dept_a["id"], [req_c], quantity=2, label="G2")

        slice_a = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={dept_b["id"]: 20, dept_a["id"]: 10},
            context={"caller_key": "keep-me"},
        )
        slice_b = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={dept_a["id"]: 10, dept_b["id"]: 20},
            context={"caller_key": "keep-me"},
        )

        assert slice_a == slice_b
        assert slice_a.context["caller_key"] == "keep-me"
        assert len(slice_a.context["requirement_group_refs"]) == 2
        assert {ref["group_id"] for ref in slice_a.context["requirement_group_refs"]} == {group1, group2}
        assert [unit.unit_id for unit in slice_a.units] == sorted([dept_a["id"], dept_b["id"]])
        assert [deviation.unit_id for deviation in slice_a.deviations] == [dept_a["id"], dept_a["id"]]
        assert slice_a.context["compatibility_status"] == "resolved"


def test_cross_site_missing_and_negative_baseline_fail_closed(app_session) -> None:
    with app_session.app_context():
        site_a, _ = SitesRepo().create_site(f"Planera 1E site A {uuid.uuid4()}")
        site_b, _ = SitesRepo().create_site(f"Planera 1E site B {uuid.uuid4()}")
        dept_a = _seed_department(site_a["id"])
        dept_b = _seed_department(site_b["id"])
        _seed_requirement_with_key(site_a["id"], "Gluten", f"req_gluten_{uuid.uuid4().hex[:8]}")

        with pytest.raises(ValueError, match="department_site_mismatch"):
            build_planning_slice_from_requirement_groups(
                site_id=site_a["id"],
                service_date=date(2026, 9, 8),
                meal_key="lunch",
                unit_baselines={dept_b["id"]: 10},
            )

        with pytest.raises(ValueError, match="department_not_found"):
            build_planning_slice_from_requirement_groups(
                site_id=site_a["id"],
                service_date=date(2026, 9, 8),
                meal_key="lunch",
                unit_baselines={str(uuid.uuid4()): 10},
            )

        with pytest.raises(ValueError, match="baseline_negative"):
            build_planning_slice_from_requirement_groups(
                site_id=site_a["id"],
                service_date=date(2026, 9, 8),
                meal_key="lunch",
                unit_baselines={dept_a["id"]: -1},
            )


def test_invalid_canonical_persistence_fails_closed(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E corrupt site {uuid.uuid4()}")
        department = _seed_department(site["id"])
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, 'Bad atomic', 'Övrigt', NULL, 'atomic', 0)"
                ),
                {"site_id": site["id"]},
            )
            db.execute(
                text(
                    "INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('bad-group-key', :department_id, 'Bad', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"department_id": department["id"]},
            )
            bad_requirement_id = db.execute(
                text("SELECT id FROM dietary_types WHERE name='Bad atomic'")
            ).fetchone()[0]
            db.execute(
                text(
                    "INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('bad-group-key', :dietary_type_id)"
                ),
                {"dietary_type_id": bad_requirement_id},
            )
            db.flush()

            with pytest.raises(ValueError, match="dietary_type_requirement_key_missing"):
                build_planning_slice_from_requirement_groups(
                    site_id=site["id"],
                    service_date=date(2026, 9, 8),
                    meal_key="lunch",
                    unit_baselines={department["id"]: 10},
                )
        finally:
            db.rollback()
            db.close()


def test_non_atomic_canonical_persistence_fails_closed(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E non atomic corrupt site {uuid.uuid4()}")
        department = _seed_department(site["id"])
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, 'Bad non atomic', 'Övrigt', 'req_bad_non_atomic', 'compound', 0)"
                ),
                {"site_id": site["id"]},
            )
            bad_non_atomic_id = db.execute(
                text("SELECT id FROM dietary_types WHERE name='Bad non atomic'")
            ).fetchone()[0]
            db.execute(
                text(
                    "INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('bad-group-non-atomic', :department_id, 'Bad non atomic', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"department_id": department["id"]},
            )
            db.execute(
                text(
                    "INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('bad-group-non-atomic', :dietary_type_id)"
                ),
                {"dietary_type_id": bad_non_atomic_id},
            )
            db.flush()

            with pytest.raises(ValueError, match="dietary_type_not_atomic"):
                build_planning_slice_from_requirement_groups(
                    site_id=site["id"],
                    service_date=date(2026, 9, 8),
                    meal_key="lunch",
                    unit_baselines={department["id"]: 10},
                )
        finally:
            db.rollback()
            db.close()


def test_cross_site_canonical_persistence_fails_closed(app_session) -> None:
    with app_session.app_context():
        site_a, _ = SitesRepo().create_site(f"Planera 1E cross site A {uuid.uuid4()}")
        site_b, _ = SitesRepo().create_site(f"Planera 1E cross site B {uuid.uuid4()}")
        department = _seed_department(site_a["id"])
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, 'Cross site', 'Övrigt', 'req_cross_site', 'atomic', 0)"
                ),
                {"site_id": site_b["id"]},
            )
            cross_site_requirement_id = db.execute(
                text("SELECT id FROM dietary_types WHERE name='Cross site'")
            ).fetchone()[0]
            db.execute(
                text(
                    "INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('bad-group-cross-site', :department_id, 'Bad cross site', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"department_id": department["id"]},
            )
            db.execute(
                text(
                    "INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('bad-group-cross-site', :dietary_type_id)"
                ),
                {"dietary_type_id": cross_site_requirement_id},
            )
            db.flush()

            with pytest.raises(ValueError, match="dietary_type_site_mismatch"):
                build_planning_slice_from_requirement_groups(
                    site_id=site_a["id"],
                    service_date=date(2026, 9, 8),
                    meal_key="lunch",
                    unit_baselines={department["id"]: 10},
                )
        finally:
            db.rollback()
            db.close()


def test_missing_requirement_relations_canonical_persistence_fails_closed(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E missing relation corrupt site {uuid.uuid4()}")
        department = _seed_department(site["id"])
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('bad-group-missing-rel', :department_id, 'Bad missing rel', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"department_id": department["id"]},
            )
            db.flush()

            with pytest.raises(ValueError, match="department_requirement_group_requirements_missing"):
                build_planning_slice_from_requirement_groups(
                    site_id=site["id"],
                    service_date=date(2026, 9, 8),
                    meal_key="lunch",
                    unit_baselines={department["id"]: 10},
                )
        finally:
            db.rollback()
            db.close()


def test_inactive_corrupted_group_still_fails_closed(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E inactive corrupt site {uuid.uuid4()}")
        department = _seed_department(site["id"])
        from core.db import get_session

        db = get_session()
        try:
            db.execute(
                text(
                    "INSERT INTO dietary_types(tenant_id, site_id, name, diet_family, requirement_key, semantics, default_select) VALUES (1, :site_id, 'Inactive bad atomic', 'Övrigt', NULL, 'atomic', 0)"
                ),
                {"site_id": site["id"]},
            )
            db.execute(
                text(
                    "INSERT INTO department_requirement_groups(id, department_id, label, default_quantity, is_active, created_at, updated_at) VALUES ('inactive-bad-group', :department_id, 'Inactive bad', 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"department_id": department["id"]},
            )
            bad_requirement_id = db.execute(
                text("SELECT id FROM dietary_types WHERE name='Inactive bad atomic'")
            ).fetchone()[0]
            db.execute(
                text(
                    "INSERT INTO department_requirement_group_requirements(group_id, dietary_type_id) VALUES ('inactive-bad-group', :dietary_type_id)"
                ),
                {"dietary_type_id": bad_requirement_id},
            )
            db.flush()

            with pytest.raises(ValueError, match="dietary_type_requirement_key_missing"):
                build_planning_slice_from_requirement_groups(
                    site_id=site["id"],
                    service_date=date(2026, 9, 8),
                    meal_key="lunch",
                    unit_baselines={department["id"]: 10},
                )
        finally:
            db.rollback()
            db.close()


def test_deviation_exceeds_baseline_adds_warning_and_compute_plan_clamps_normal(app_session) -> None:
    with app_session.app_context():
        site, _ = SitesRepo().create_site(f"Planera 1E warning site {uuid.uuid4()}")
        department = _seed_department(site["id"])
        requirement_id = _seed_requirement_with_key(site["id"], "Gluten", f"req_gluten_{uuid.uuid4().hex[:8]}")
        _create_group(site["id"], department["id"], [requirement_id], quantity=2, label="Too much")

        slice_ = build_planning_slice_from_requirement_groups(
            site_id=site["id"],
            service_date=date(2026, 9, 8),
            meal_key="lunch",
            unit_baselines={department["id"]: 1},
        )
        result = compute_plan(slice_.to_plan_request())

        assert slice_.deviations[0].quantity == 2
        assert slice_.warnings == (f"unit[{department['id']}] canonical deviations exceed baseline",)
        assert result.totals.baseline_total == 1
        assert result.totals.deviation_total == 2
        assert result.totals.normal_total == 0
