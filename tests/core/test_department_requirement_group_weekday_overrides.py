from __future__ import annotations

from datetime import date, timedelta
import uuid

import pytest

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo
from core.department_requirement_group_quantity_resolver import resolve_effective_quantity


def _seed_group_with_requirements(site_name: str = "Weekday override site", requirement_count: int = 1):
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


def test_weekday_override_repo_crud_and_validation(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(requirement_count=2)
        repo = DepartmentRequirementGroupWeekdayOverridesRepo()
        group_repo = DepartmentRequirementGroupsRepo()

        assert repo.resolve_effective_quantity(group["id"], 1, "lunch", 2) == 2

        created = repo.set_override(group["id"], 1, " Lunch ", 3)
        assert created == {"group_id": group["id"], "weekday": 1, "meal_key": "lunch", "quantity": 3}
        assert repo.get_override(group["id"], 1, "lunch") == created
        assert repo.resolve_effective_quantity(group["id"], 1, "lunch", 2) == 3
        assert repo.resolve_effective_quantity(group["id"], 1, "dinner", 2) == 2
        assert repo.resolve_effective_quantity(group["id"], 2, "lunch", 2) == 2

        zero_override = repo.set_override(group["id"], 1, "lunch", 0)
        assert zero_override["quantity"] == 0
        assert repo.resolve_effective_quantity(group["id"], 1, "lunch", 2) == 0

        rows = repo.list_for_group(group["id"])
        assert rows == [{"group_id": group["id"], "weekday": 1, "meal_key": "lunch", "quantity": 0}]

        deleted = repo.delete_override(group["id"], 1, "lunch")
        assert deleted is True
        assert repo.resolve_effective_quantity(group["id"], 1, "lunch", 2) == 2

        with pytest.raises(ValueError, match="weekday_invalid"):
            repo.set_override(group["id"], 0, "lunch", 1)
        with pytest.raises(ValueError, match="meal_key_empty"):
            repo.set_override(group["id"], 1, "   ", 1)
        with pytest.raises(ValueError, match="quantity_negative"):
            repo.set_override(group["id"], 1, "lunch", -1)
        with pytest.raises(ValueError, match="department_requirement_group_not_found"):
            repo.set_override(str(uuid.uuid4()), 1, "lunch", 1)

        before = group_repo.get_group(group["id"])
        assert before is not None
        assert len(before["requirements"]) == 2


def test_effective_quantity_resolver_prefers_exact_then_weekday_then_default(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Resolver precedence site")
        weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
        exact_repo = DepartmentRequirementGroupServiceOverridesRepo()

        service_date = date(2026, 9, 8)
        same_weekday_next_week = service_date + timedelta(days=7)

        weekday_repo.set_override(group["id"], service_date.isoweekday(), "lunch", 4)
        assert resolve_effective_quantity(group["id"], service_date, "lunch") == 4
        assert resolve_effective_quantity(group["id"], same_weekday_next_week, "lunch") == 4
        assert resolve_effective_quantity(group["id"], service_date, "dinner") == 2

        exact_repo.set_override(group["id"], service_date, "lunch", 9)
        assert resolve_effective_quantity(group["id"], service_date, "lunch") == 9

        weekday_repo.set_override(group["id"], service_date.isoweekday(), "lunch", 0)
        assert resolve_effective_quantity(group["id"], service_date, "lunch") == 9


def test_weekday_quantity_applies_to_thursday_lunch_and_recurs_next_week(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Thursday lunch recurrence site")
        repo = DepartmentRequirementGroupWeekdayOverridesRepo()

        thursday_lunch = date(2026, 9, 10)
        assert thursday_lunch.isoweekday() == 4
        next_thursday_lunch = thursday_lunch + timedelta(days=7)
        assert next_thursday_lunch.isoweekday() == 4
        friday_lunch = thursday_lunch + timedelta(days=1)
        assert friday_lunch.isoweekday() == 5
        thursday_dinner = thursday_lunch

        repo.set_override(group["id"], thursday_lunch.isoweekday(), "lunch", 1)

        assert resolve_effective_quantity(group["id"], thursday_lunch, "lunch") == 1
        assert resolve_effective_quantity(group["id"], next_thursday_lunch, "lunch") == 1
        assert resolve_effective_quantity(group["id"], friday_lunch, "lunch") == 2
        assert resolve_effective_quantity(group["id"], thursday_dinner, "dinner") == 2


def test_weekday_zero_override_and_reset_fall_back_to_default(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Zero and reset site")
        repo = DepartmentRequirementGroupWeekdayOverridesRepo()

        thursday_lunch = date(2026, 9, 10)
        assert thursday_lunch.isoweekday() == 4

        repo.set_override(group["id"], thursday_lunch.isoweekday(), "lunch", 0)
        assert resolve_effective_quantity(group["id"], thursday_lunch, "lunch") == 0

        repo.set_override(group["id"], thursday_lunch.isoweekday(), "lunch", 1)
        assert resolve_effective_quantity(group["id"], thursday_lunch, "lunch") == 1

        deleted = repo.delete_override(group["id"], thursday_lunch.isoweekday(), "lunch")
        assert deleted is True
        assert resolve_effective_quantity(group["id"], thursday_lunch, "lunch") == 2


def test_exact_thursday_override_beats_weekday_override_and_next_thursday_uses_weekday(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Exact precedence site")
        weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
        exact_repo = DepartmentRequirementGroupServiceOverridesRepo()

        thursday_lunch = date(2026, 9, 10)
        assert thursday_lunch.isoweekday() == 4
        next_thursday_lunch = thursday_lunch + timedelta(days=7)
        assert next_thursday_lunch.isoweekday() == 4

        weekday_repo.set_override(group["id"], thursday_lunch.isoweekday(), "lunch", 1)
        exact_repo.set_override(group["id"], thursday_lunch, "lunch", 0)

        assert resolve_effective_quantity(group["id"], thursday_lunch, "lunch") == 0
        assert resolve_effective_quantity(group["id"], next_thursday_lunch, "lunch") == 1


def test_weekday_negative_quantity_is_rejected(app_session) -> None:
    with app_session.app_context():
        _site, _department, group = _seed_group_with_requirements(site_name="Negative weekday quantity site")
        repo = DepartmentRequirementGroupWeekdayOverridesRepo()

        with pytest.raises(ValueError, match="quantity_negative"):
            repo.set_override(group["id"], 4, "lunch", -1)
