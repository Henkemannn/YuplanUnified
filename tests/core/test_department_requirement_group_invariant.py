from __future__ import annotations

from datetime import date
import uuid

import pytest

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.db import get_session
from core.department_requirement_group_invariant import RequirementCountExceededError, resolve_effective_special_diet_total_in_session
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo


def _seed_department(*, resident_count: int) -> tuple[dict, dict]:
    site, _ = SitesRepo().create_site(f"Invariant site {uuid.uuid4()}")
    department, _ = DepartmentsRepo().create_department(
        site_id=site["id"],
        name=f"Invariant department {uuid.uuid4()}",
        resident_count_mode="fixed",
        resident_count_fixed=resident_count,
    )
    return site, department


def _seed_requirement(site_id: str, name: str) -> int:
    return DietTypesRepo().create(site_id=site_id, name=name, default_select=False, semantics="atomic")


def test_default_special_diet_total_equal_to_residents_passes_and_above_rejects(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(resident_count=12)
        requirement_id = _seed_requirement(site["id"], "Timbal")
        repo = DepartmentRequirementGroupsRepo()

        group = repo.create_group(department["id"], 12, [requirement_id], label="Timbal")
        assert group["default_quantity"] == 12
        db = get_session()
        try:
            assert resolve_effective_special_diet_total_in_session(db, department["id"]) == 12
        finally:
            db.close()

        with pytest.raises(RequirementCountExceededError):
            repo.create_group(department["id"], 13, [requirement_id], label="Too many")


def test_no_silent_clamp_on_default_quantity_rejection(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(resident_count=12)
        requirement_id = _seed_requirement(site["id"], "Timbal")
        repo = DepartmentRequirementGroupsRepo()

        group = repo.create_group(department["id"], 12, [requirement_id], label="Timbal")
        group_id = str(group["id"])

        with pytest.raises(RequirementCountExceededError):
            repo.update_group(group_id, default_quantity=13)

        reread = repo.get_group(group_id)
        assert reread is not None
        assert reread["default_quantity"] == 12


def test_composite_group_quantity_is_counted_once(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(resident_count=12)
        timbal_id = _seed_requirement(site["id"], "Timbal")
        glutenfri_id = _seed_requirement(site["id"], "Glutenfri")
        repo = DepartmentRequirementGroupsRepo()

        group = repo.create_group(department["id"], 2, [timbal_id, glutenfri_id], label="Timbal + Glutenfri")

        assert group["default_quantity"] == 2
        assert len(group["requirements"]) == 2
        assert {item["dietary_type_id"] for item in group["requirements"]} == {timbal_id, glutenfri_id}


def test_multiple_groups_sum_and_overflow(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(resident_count=12)
        timbal_id = _seed_requirement(site["id"], "Timbal")
        glutenfri_id = _seed_requirement(site["id"], "Glutenfri")
        vegan_id = _seed_requirement(site["id"], "Vegan")
        repo = DepartmentRequirementGroupsRepo()

        repo.create_group(department["id"], 2, [timbal_id, glutenfri_id], label="Timbal + Glutenfri")
        vegan_group = repo.create_group(department["id"], 10, [vegan_id], label="Vegan")
        db = get_session()
        try:
            assert resolve_effective_special_diet_total_in_session(db, department["id"]) == 12
        finally:
            db.close()

        with pytest.raises(RequirementCountExceededError):
            repo.update_group(str(vegan_group["id"]), default_quantity=11)


def test_edit_replacement_math_uses_proposed_final_total(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(resident_count=12)
        a_id = _seed_requirement(site["id"], "A")
        b_id = _seed_requirement(site["id"], "B")
        repo = DepartmentRequirementGroupsRepo()

        group = repo.create_group(department["id"], 5, [a_id], label="A")
        repo.create_group(department["id"], 5, [b_id], label="B")

        updated = repo.update_group(str(group["id"]), default_quantity=7)
        assert updated is not None
        db = get_session()
        try:
            assert resolve_effective_special_diet_total_in_session(db, department["id"]) == 12
        finally:
            db.close()

        with pytest.raises(RequirementCountExceededError):
            repo.update_group(str(group["id"]), default_quantity=8)


def test_remove_group_lowers_total(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(resident_count=12)
        a_id = _seed_requirement(site["id"], "A")
        b_id = _seed_requirement(site["id"], "B")
        repo = DepartmentRequirementGroupsRepo()

        group_a = repo.create_group(department["id"], 7, [a_id], label="A")
        group_b = repo.create_group(department["id"], 5, [b_id], label="B")

        deactivated = repo.update_group(str(group_b["id"]), is_active=False)
        assert deactivated is not None and deactivated["is_active"] is False
        db = get_session()
        try:
            assert resolve_effective_special_diet_total_in_session(db, department["id"]) == 7
        finally:
            db.close()


def test_weekday_and_exact_date_caps_use_aggregate_resident_counts(app_session) -> None:
    with app_session.app_context():
        site, department = _seed_department(resident_count=6)
        timbal_id = _seed_requirement(site["id"], "Timbal")
        vegan_id = _seed_requirement(site["id"], "Vegan")
        repo = DepartmentRequirementGroupsRepo()
        weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
        exact_repo = DepartmentRequirementGroupServiceOverridesRepo()

        group_a = repo.create_group(department["id"], 2, [timbal_id], label="Timbal")
        group_b = repo.create_group(department["id"], 4, [vegan_id], label="Vegan")

        assert weekday_repo.set_override(str(group_a["id"]), 2, "lunch", 2)["quantity"] == 2
        assert exact_repo.set_override(str(group_a["id"]), date(2026, 10, 6), "lunch", 2)["quantity"] == 2
        assert exact_repo.set_override(str(group_b["id"]), date(2026, 10, 6), "lunch", 4)["quantity"] == 4

        with pytest.raises(RequirementCountExceededError):
            weekday_repo.set_override(str(group_b["id"]), 2, "lunch", 5)
        with pytest.raises(RequirementCountExceededError):
            exact_repo.set_override(str(group_b["id"]), date(2026, 10, 6), "lunch", 5)
