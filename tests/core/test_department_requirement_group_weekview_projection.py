from __future__ import annotations

from datetime import date
import uuid

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.department_requirement_group_service_overrides_repo import DepartmentRequirementGroupServiceOverridesRepo
from core.department_requirement_group_weekday_overrides_repo import DepartmentRequirementGroupWeekdayOverridesRepo
from core.department_requirement_group_weekview_projection import build_department_requirement_group_weekview_projection


def _seed_site_department_and_requirements(site_name: str = "Weekview projection site"):
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
    timbal_id = diet_repo.create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    glutenfri_id = diet_repo.create(site_id=site["id"], name="Glutenfri", default_select=False, semantics="atomic")
    lactosefri_id = diet_repo.create(site_id=site["id"], name="Laktosfri", default_select=False, semantics="atomic")
    return site, department, group_repo, timbal_id, glutenfri_id, lactosefri_id


def test_singleton_quantity_two_projects_one_item(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, _glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements()
        group = group_repo.create_group(
            department["id"],
            2,
            [timbal_id],
            label="Timbal",
            primary_requirement_id=timbal_id,
        )

        projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=date(2026, 10, 8),
            meal_key="lunch",
        )

        assert projection.department_id == department["id"]
        assert projection.service_date == "2026-10-08"
        assert projection.meal_key == "lunch"
        assert len(projection.needs) == 1
        need = projection.needs[0]
        assert need.group_id == group["id"]
        assert need.primary_requirement_id == timbal_id
        assert need.primary_label == "Timbal"
        assert need.modifier_labels == ()
        assert need.member_labels == ("Timbal",)
        assert need.effective_quantity == 2
        assert need.marked is False


def test_primary_and_modifier_semantics_and_same_member_set_primary_order(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements("Primary semantics site")
        group = group_repo.create_group(
            department["id"],
            1,
            [timbal_id, glutenfri_id],
            label=None,
            primary_requirement_id=timbal_id,
        )
        other_group = group_repo.create_group(
            department["id"],
            1,
            [glutenfri_id, timbal_id],
            label=None,
            primary_requirement_id=glutenfri_id,
        )

        projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=date(2026, 10, 8),
            meal_key="lunch",
        )

        projected = {need.group_id: need for need in projection.needs}
        first = projected[group["id"]]
        second = projected[other_group["id"]]
        assert first.primary_label == "Timbal"
        assert set(first.modifier_labels) == {"Glutenfri"}
        assert second.primary_label == "Glutenfri"
        assert set(second.modifier_labels) == {"Timbal"}


def test_composite_group_display_label_prefers_member_names_over_stale_single_label(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements("Stale label site")
        group = group_repo.create_group(
            department["id"],
            2,
            [timbal_id, glutenfri_id],
            label="Timbal",
            primary_requirement_id=timbal_id,
        )

        projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=date(2026, 10, 8),
            meal_key="lunch",
        )

        need = next(item for item in projection.needs if item.group_id == group["id"])
        assert need.display_label == "Timbal + Glutenfri"
        assert need.primary_label == "Timbal"
        assert set(need.modifier_labels) == {"Glutenfri"}


def test_unresolved_group_keeps_exact_combination_without_guessing_primary(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements("Unresolved site")
        group = group_repo.create_group(
            department["id"],
            2,
            [timbal_id, glutenfri_id],
            label="Legacy unresolved",
            primary_requirement_id=None,
        )

        projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=date(2026, 10, 8),
            meal_key="lunch",
        )

        need = projection.needs[0]
        assert need.group_id == group["id"]
        assert need.unresolved_primary is True
        assert need.primary_requirement_id is None
        assert need.primary_label is None
        assert set(need.member_labels) == {"Timbal", "Glutenfri"}
        assert "Timbal" in need.display_label
        assert "Glutenfri" in need.display_label


def test_default_weekday_exact_override_and_zero_omits_active_need(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements("Quantity site")
        group = group_repo.create_group(
            department["id"],
            2,
            [timbal_id, glutenfri_id],
            label="Timbal + Glutenfri",
            primary_requirement_id=timbal_id,
        )
        weekday_repo = DepartmentRequirementGroupWeekdayOverridesRepo()
        exact_repo = DepartmentRequirementGroupServiceOverridesRepo()
        thursday = date(2026, 10, 8)
        assert thursday.isoweekday() == 4

        projection_default = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=thursday,
            meal_key="lunch",
        )
        assert projection_default.needs[0].effective_quantity == 2

        weekday_repo.set_override(group["id"], thursday.isoweekday(), "lunch", 1)
        projection_weekday = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=thursday,
            meal_key="lunch",
        )
        assert projection_weekday.needs[0].effective_quantity == 1

        exact_repo.set_override(group["id"], thursday, "lunch", 3)
        projection_exact = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=thursday,
            meal_key="lunch",
        )
        assert projection_exact.needs[0].effective_quantity == 3

        exact_repo.set_override(group["id"], thursday, "lunch", 0)
        projection_zero = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=thursday,
            meal_key="lunch",
        )
        assert projection_zero.needs == ()


def test_inactive_group_is_omitted_from_weekview_projection(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements("Inactive group site")
        group = group_repo.create_group(
            department["id"],
            2,
            [timbal_id, glutenfri_id],
            label="Timbal + Glutenfri",
            primary_requirement_id=timbal_id,
        )
        group_repo.update_group(group["id"], is_active=False)

        projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=date(2026, 10, 8),
            meal_key="lunch",
        )

        assert projection.needs == ()

def test_completion_true_false_missing_and_date_meal_independence(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements("Completion projection site")
        group = group_repo.create_group(
            department["id"],
            2,
            [timbal_id, glutenfri_id],
            label="Timbal + Glutenfri",
            primary_requirement_id=timbal_id,
        )
        completion_repo = DepartmentRequirementGroupCompletionRepo()
        service_date = date(2026, 10, 8)
        next_day = date(2026, 10, 9)

        projection_missing = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=service_date,
            meal_key="lunch",
        )
        assert projection_missing.needs[0].marked is False

        completion_repo.set_marked(department["id"], group["id"], service_date, "lunch", True)
        projection_true = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=service_date,
            meal_key="lunch",
        )
        assert projection_true.needs[0].marked is True

        completion_repo.set_marked(department["id"], group["id"], service_date, "lunch", False)
        projection_false = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=service_date,
            meal_key="lunch",
        )
        assert projection_false.needs[0].marked is False

        projection_other_meal = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=service_date,
            meal_key="dinner",
        )
        assert projection_other_meal.needs[0].marked is False

        projection_other_day = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=next_day,
            meal_key="lunch",
        )
        assert projection_other_day.needs[0].marked is False


def test_two_groups_same_primary_remain_separate_and_member_count_does_not_split_completion(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, lactosefri_id = _seed_site_department_and_requirements("Separate groups site")
        group_one = group_repo.create_group(
            department["id"],
            1,
            [timbal_id, glutenfri_id],
            label="Group 1",
            primary_requirement_id=timbal_id,
        )
        group_two = group_repo.create_group(
            department["id"],
            1,
            [timbal_id, lactosefri_id],
            label="Group 2",
            primary_requirement_id=timbal_id,
        )
        completion_repo = DepartmentRequirementGroupCompletionRepo()
        service_date = date(2026, 10, 8)
        completion_repo.set_marked(department["id"], group_one["id"], service_date, "lunch", True)

        projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=service_date,
            meal_key="lunch",
        )

        assert len(projection.needs) == 2
        need_by_group = {need.group_id: need for need in projection.needs}
        assert need_by_group[group_one["id"]].marked is True
        assert need_by_group[group_two["id"]].marked is False
        assert need_by_group[group_one["id"]].effective_quantity == 1
        assert need_by_group[group_two["id"]].effective_quantity == 1
        assert len({need.group_id for need in projection.needs}) == 2


def test_completion_mark_reload_flips_projection_marked_state(app_session) -> None:
    with app_session.app_context():
        site, department, group_repo, timbal_id, glutenfri_id, _lactosefri_id = _seed_site_department_and_requirements("Reload site")
        group = group_repo.create_group(
            department["id"],
            1,
            [timbal_id, glutenfri_id],
            label=None,
            primary_requirement_id=timbal_id,
        )
        completion_repo = DepartmentRequirementGroupCompletionRepo()
        service_date = date(2026, 10, 8)

        completion_repo.set_marked(department["id"], group["id"], service_date, "lunch", True)
        marked_projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=service_date,
            meal_key="lunch",
        )
        assert marked_projection.needs[0].marked is True

        completion_repo.set_marked(department["id"], group["id"], service_date, "lunch", False)
        cleared_projection = build_department_requirement_group_weekview_projection(
            tenant_id=None,
            site_id=site["id"],
            department_id=department["id"],
            service_date=service_date,
            meal_key="lunch",
        )
        assert cleared_projection.needs[0].marked is False
