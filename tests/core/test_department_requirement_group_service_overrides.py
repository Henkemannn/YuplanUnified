from __future__ import annotations

from datetime import date
import uuid

import pytest

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import (
    DepartmentRequirementGroupServiceOverridesRepo,
)


def _seed_group_with_requirements(site_name: str = "Service override site", requirement_count: int = 1):
    site_repo = SitesRepo()
    dept_repo = DepartmentsRepo()
    diet_repo = DietTypesRepo()
    group_repo = DepartmentRequirementGroupsRepo()

    site, _ = site_repo.create_site(site_name)
    department, _ = dept_repo.create_department(
        site_id=site["id"],
        name=f"Department {uuid.uuid4()}",
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    requirement_ids = []
    for index in range(requirement_count):
        requirement_ids.append(
            diet_repo.create(
                site_id=site["id"],
                name=f"Requirement {index} {uuid.uuid4()}",
                default_select=False,
                semantics="atomic",
            )
        )
    group = group_repo.create_group(department["id"], 2, requirement_ids, label="Group")
    return site, department, group


def test_effective_quantity_fallback_override_isolation_zero_delete_inactive_reactivate_and_conservation(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(requirement_count=2)
        repo = DepartmentRequirementGroupServiceOverridesRepo()
        group_repo = DepartmentRequirementGroupsRepo()
        service_date = date(2026, 9, 8)

        assert repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 2

        repo.set_override(group["id"], "2026-09-08", "lunch", 3)
        assert repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 3
        assert repo.resolve_effective_quantity(group["id"], service_date, "dinner") == 2
        assert repo.resolve_effective_quantity(group["id"], date(2026, 9, 9), "lunch") == 2

        zero_override = repo.set_override(group["id"], service_date, "lunch", 0)
        assert zero_override["quantity"] == 0
        assert repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 0

        repo.set_override(group["id"], service_date, "lunch", 5)
        assert repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 5
        reloaded = group_repo.get_group(group["id"])
        assert reloaded is not None
        assert len(reloaded["requirements"]) == 2

        deleted = repo.delete_override(group["id"], service_date, "lunch")
        assert deleted is True
        assert repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 2

        repo.set_override(group["id"], service_date, "lunch", 7)
        deactivated = group_repo.update_group(group["id"], is_active=False)
        assert deactivated is not None and deactivated["is_active"] is False
        assert repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 0

        reactivated = group_repo.update_group(group["id"], is_active=True)
        assert reactivated is not None and reactivated["is_active"] is True
        assert repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 7


def test_duplicate_key_upserts_single_row_and_list_is_deterministic(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Duplicate key site")
        repo = DepartmentRequirementGroupServiceOverridesRepo()

        first = repo.set_override(group["id"], "2026-09-08", " Lunch ", 2)
        second = repo.set_override(group["id"], date(2026, 9, 8), "lunch", 5)

        assert first["meal_key"] == "lunch"
        assert second["meal_key"] == "lunch"
        assert second["quantity"] == 5
        assert repo.resolve_effective_quantity(group["id"], date(2026, 9, 8), "lunch") == 5

        repo.set_override(group["id"], date(2026, 9, 9), "dinner", 1)
        rows = repo.list_for_group(group["id"])
        assert [row["service_date"] for row in rows] == ["2026-09-08", "2026-09-09"]
        assert [row["meal_key"] for row in rows] == ["lunch", "dinner"]
        assert len(rows) == 2


def test_override_validation_and_requirements_immutability(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Validation site", requirement_count=2)
        repo = DepartmentRequirementGroupServiceOverridesRepo()
        group_repo = DepartmentRequirementGroupsRepo()
        before = group_repo.get_group(group["id"])
        assert before is not None

        with pytest.raises(ValueError, match="meal_key_empty"):
            repo.set_override(group["id"], date(2026, 9, 8), "   ", 1)
        with pytest.raises(ValueError, match="service_date_invalid"):
            repo.set_override(group["id"], "not-a-date", "lunch", 1)
        with pytest.raises(ValueError, match="quantity_negative"):
            repo.set_override(group["id"], date(2026, 9, 8), "lunch", -1)
        with pytest.raises(ValueError, match="department_requirement_group_not_found"):
            repo.set_override(str(uuid.uuid4()), date(2026, 9, 8), "lunch", 1)

        repo.set_override(group["id"], date(2026, 9, 8), "lunch", 3)
        repo.delete_override(group["id"], date(2026, 9, 8), "lunch")

        after = group_repo.get_group(group["id"])
        assert after is not None
        assert before["requirements"] == after["requirements"]


def test_internal_resolution_does_not_depend_on_public_get_override(app_session, monkeypatch) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Nested call site", requirement_count=1)
        repo = DepartmentRequirementGroupServiceOverridesRepo()
        repo.set_override(group["id"], date(2026, 9, 8), "lunch", 4)

        def _boom(*args, **kwargs):
            raise AssertionError("public get_override must not be called here")

        monkeypatch.setattr(repo, "get_override", _boom)
        assert repo.resolve_effective_quantity(group["id"], date(2026, 9, 8), "lunch") == 4
        assert repo.resolve_effective_quantity(group["id"], date(2026, 9, 9), "lunch") == 2
