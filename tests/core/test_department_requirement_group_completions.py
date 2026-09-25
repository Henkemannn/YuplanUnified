from __future__ import annotations

from datetime import date
import uuid

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietDefaultsRepo, DietTypesRepo, SitesRepo, DepartmentDietOverridesRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo
from core.db import get_session


def _seed_group(site_name: str = "Completion site", requirement_count: int = 2):
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
    group = group_repo.create_group(
        department["id"],
        2,
        requirement_ids,
        label="Group",
        primary_requirement_id=requirement_ids[0],
    )
    return site, department, group, requirement_ids


def _ensure_legacy_weekview_table() -> None:
    db = get_session()
    try:
        db.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS weekview_registrations (
                tenant_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                week INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                meal TEXT NOT NULL,
                diet_type TEXT NOT NULL,
                marked INTEGER NOT NULL DEFAULT 0,
                UNIQUE (tenant_id, department_id, year, week, day_of_week, meal, diet_type)
            )
            """
            )
        )
        db.commit()
    finally:
        db.close()


def test_group_completion_true_false_and_date_meal_isolation(app_session) -> None:
    with app_session.app_context():
        _site, department, group, _requirements = _seed_group()
        repo = DepartmentRequirementGroupCompletionRepo()

        thursday_lunch = date(2026, 10, 1)
        thursday_dinner = date(2026, 10, 1)
        next_date = date(2026, 10, 2)

        assert repo.get(group["id"], thursday_lunch, "lunch") is None

        marked = repo.set_marked(department["id"], group["id"], thursday_lunch, "lunch", True)
        assert marked == {"group_id": group["id"], "service_date": "2026-10-01", "meal_key": "lunch", "marked": True}
        assert repo.get(group["id"], thursday_lunch, "lunch") == marked
        assert repo.get(group["id"], thursday_dinner, "dinner") is None
        assert repo.get(group["id"], next_date, "lunch") is None

        unmarked = repo.set_marked(department["id"], group["id"], thursday_lunch, "lunch", False)
        assert unmarked["marked"] is False
        assert repo.get(group["id"], thursday_lunch, "lunch") == unmarked


def test_group_completion_one_row_for_multi_member_group_and_membership_order_is_ignored(app_session) -> None:
    with app_session.app_context():
        _site, department, group, requirement_ids = _seed_group(requirement_count=2)
        repo = DepartmentRequirementGroupCompletionRepo()
        group_repo = DepartmentRequirementGroupsRepo()

        service_date = date(2026, 10, 1)
        repo.set_marked(department["id"], group["id"], service_date, "lunch", True)

        rows = repo.list_for_department_date_range(group_repo.get_group(group["id"])["department_id"], service_date, service_date)
        assert rows == [{"group_id": group["id"], "service_date": "2026-10-01", "meal_key": "lunch", "marked": True}]

        group_repo.update_group(group["id"], primary_requirement_id=requirement_ids[1])
        after_primary_change = repo.get(group["id"], service_date, "lunch")
        assert after_primary_change is not None and after_primary_change["marked"] is True


def test_separate_groups_same_primary_remain_separate_and_invalid_group_rejected(app_session) -> None:
    with app_session.app_context():
        _site, department, group_a, requirement_ids = _seed_group(site_name="Separate groups site")
        group_b = DepartmentRequirementGroupsRepo().create_group(
            department["id"],
            2,
            requirement_ids,
            label="Group B",
            primary_requirement_id=requirement_ids[0],
        )
        repo = DepartmentRequirementGroupCompletionRepo()
        service_date = date(2026, 10, 1)

        repo.set_marked(department["id"], group_a["id"], service_date, "lunch", True)
        assert repo.get(group_a["id"], service_date, "lunch") is not None
        assert repo.get(group_b["id"], service_date, "lunch") is None

        with pytest.raises(ValueError, match="department_requirement_group_not_found"):
            repo.set_marked(department["id"], str(uuid.uuid4()), service_date, "lunch", True)


def test_completion_validation_and_no_side_effects_on_overrides_or_legacy_registrations(app_session) -> None:
    with app_session.app_context():
        _site, department, group, requirement_ids = _seed_group(site_name="Side effects site")
        completion_repo = DepartmentRequirementGroupCompletionRepo()
        weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
        exact_repo = DepartmentRequirementGroupServiceOverridesRepo()
        group_repo = DepartmentRequirementGroupsRepo()
        dept_repo = DepartmentsRepo()

        service_date = date(2026, 10, 1)
        dept_repo.upsert_department_diet_defaults(
            department["id"],
            expected_version=0,
            items=[{"diet_type_id": requirement_ids[0], "default_count": 3}],
        )
        legacy_override_repo = DepartmentDietOverridesRepo()
        legacy_override_repo.replace_for_department_diet(
            department["id"],
            requirement_ids[0],
            [{"day": 4, "meal": "lunch", "count": 9}],
        )
        default_rows_before = DietDefaultsRepo().list_for_department(department["id"])
        legacy_overrides_before = legacy_override_repo.list_for_department(department["id"])
        weekday_repo.set_override(group["id"], service_date.isoweekday(), "lunch", 1)
        exact_repo.set_override(group["id"], service_date, "lunch", 0)
        before_group = group_repo.get_group(group["id"])
        assert before_group is not None

        _ensure_legacy_weekview_table()
        db = get_session()
        try:
            before_legacy = int(
                db.execute(text("SELECT COUNT(*) FROM weekview_registrations")).scalar_one()
            )
        finally:
            db.close()

        with pytest.raises(ValueError, match="meal_key_invalid"):
            completion_repo.set_marked(department["id"], group["id"], service_date, "breakfast", True)
        with pytest.raises(ValueError, match="service_date_invalid"):
            completion_repo.set_marked(department["id"], group["id"], "not-a-date", "lunch", True)

        completion_repo.set_marked(department["id"], group["id"], service_date, "lunch", True)
        completion_repo.set_marked(department["id"], group["id"], service_date, "lunch", False)

        after_group = group_repo.get_group(group["id"])
        assert after_group is not None
        assert before_group["default_quantity"] == after_group["default_quantity"]
        assert before_group["requirements"] == after_group["requirements"]
        assert weekday_repo.resolve_effective_quantity(group["id"], service_date.isoweekday(), "lunch", 2) == 1
        assert exact_repo.resolve_effective_quantity(group["id"], service_date, "lunch") == 0
        assert DietDefaultsRepo().list_for_department(department["id"]) == default_rows_before
        assert legacy_override_repo.list_for_department(department["id"]) == legacy_overrides_before

        db = get_session()
        try:
            after_legacy = int(
                db.execute(text("SELECT COUNT(*) FROM weekview_registrations")).scalar_one()
            )
        finally:
            db.close()
        assert before_legacy == after_legacy


def test_completion_rejects_cross_department_group_and_leaves_no_row(app_session) -> None:
    with app_session.app_context():
        _site, department_a, group_a, _requirements_a = _seed_group(site_name="Department A")
        _site_b, department_b, group_b, _requirements_b = _seed_group(site_name="Department B")
        repo = DepartmentRequirementGroupCompletionRepo()
        service_date = date(2026, 10, 1)

        with pytest.raises(ValueError, match="department_requirement_group_not_owned"):
            repo.set_marked(department_a["id"], group_b["id"], service_date, "lunch", True)

        assert repo.get(group_b["id"], service_date, "lunch") is None
        assert repo.get(group_a["id"], service_date, "lunch") is None
        assert repo.list_for_department_date_range(department_a["id"], service_date, service_date) == []
        assert repo.list_for_department_date_range(department_b["id"], service_date, service_date) == []
