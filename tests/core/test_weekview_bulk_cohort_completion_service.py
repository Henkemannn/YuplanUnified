from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.db import get_session
from core.weekview.cohort_bulk_completion_service import (
    CohortBulkCompletionError,
    CohortBulkCompletionTarget,
    WeekviewCohortBulkCompletionService,
)
from core.weekview.cohort_completion_service import CohortWeekviewStaleError
from core.weekview.repo import WeekviewRepo


def _seed_group(site_name: str, department_name: str, group_label: str = "Group") -> tuple[str, str, str, list[int]]:
    site_repo = SitesRepo()
    dept_repo = DepartmentsRepo()
    diet_repo = DietTypesRepo()
    group_repo = DepartmentRequirementGroupsRepo()

    site, _ = site_repo.create_site(site_name)
    department, _ = dept_repo.create_department(
        site_id=site["id"],
        name=department_name,
        resident_count_mode="fixed",
        resident_count_fixed=10,
    )
    timbal_id = diet_repo.create(site_id=site["id"], name="Timbal", default_select=False, semantics="atomic")
    lactose_id = diet_repo.create(site_id=site["id"], name="Laktosfri", default_select=False, semantics="atomic")
    group = group_repo.create_group(
        department["id"],
        1,
        [timbal_id, lactose_id],
        label=group_label,
        primary_requirement_id=timbal_id,
    )
    return site["id"], department["id"], str(group["id"]), [timbal_id, lactose_id]


def _create_group_in_department(department_id: str, requirement_ids: list[int], *, group_label: str) -> str:
    group = DepartmentRequirementGroupsRepo().create_group(
        department_id,
        1,
        requirement_ids,
        label=group_label,
        primary_requirement_id=requirement_ids[0],
    )
    return str(group["id"])


def _seed_version(tenant_id: int, department_id: str, year: int, week: int, version: int) -> None:
    WeekviewRepo().get_version(tenant_id=tenant_id, year=year, week=week, department_id=department_id)
    db = get_session()
    try:
        db.execute(
            text(
                """
                INSERT INTO weekview_versions(tenant_id, department_id, year, week, version)
                VALUES(:tenant_id, :department_id, :year, :week, :version)
                ON CONFLICT(tenant_id, department_id, year, week)
                DO UPDATE SET version=excluded.version
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "department_id": department_id,
                "year": year,
                "week": week,
                "version": version,
            },
        )
        db.commit()
    finally:
        db.close()


def _version(tenant_id: int, department_id: str, year: int, week: int) -> int:
    return WeekviewRepo().get_version(tenant_id=tenant_id, year=year, week=week, department_id=department_id)


def _completion(group_id: str, *, service_date: date = date(2026, 9, 21), meal: str = "lunch") -> dict[str, object] | None:
    return DepartmentRequirementGroupCompletionRepo().get(group_id, service_date, meal)


def _ensure_weekview_registrations_table() -> None:
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


def _target(department_id: str, group_id: str, *, service_date: date = date(2026, 9, 21), meal: str = "lunch") -> CohortBulkCompletionTarget:
    return CohortBulkCompletionTarget(
        department_id=department_id,
        group_id=group_id,
        service_date=service_date,
        meal=meal,
    )


def test_bulk_write_success_single_department_single_target(app_session) -> None:
    tenant_id = 1
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id, _requirements = _seed_group("Bulk success site", "Bulk success department")
        _seed_version(tenant_id, department_id, year, week, 0)
        _ensure_weekview_registrations_table()

        result = WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
            tenant_id=tenant_id,
            year=year,
            week=week,
            expected_base_versions={department_id: 0},
            targets=[_target(department_id, group_id)],
            marked=True,
        )

        assert result == {"marked": True, "target_count": 1, "departments": {department_id: 1}}
        assert _version(tenant_id, department_id, year, week) == 1
        assert _completion(group_id)["marked"] is True
        db = get_session()
        try:
            assert int(db.execute(text("SELECT COUNT(*) FROM weekview_registrations")).scalar_one()) == 0
        finally:
            db.close()


def test_bulk_write_success_single_department_multiple_targets_bumps_once(app_session) -> None:
    tenant_id = 2
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_a, requirement_ids = _seed_group("Bulk multi target site", "Bulk multi target department A", group_label="Group A")
        group_b = _create_group_in_department(department_id, requirement_ids, group_label="Group B")
        _seed_version(tenant_id, department_id, year, week, 0)

        result = WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
            tenant_id=tenant_id,
            year=year,
            week=week,
            expected_base_versions={department_id: 0},
            targets=[_target(department_id, group_a), _target(department_id, group_b)],
            marked=True,
        )

        assert result["marked"] is True
        assert result["target_count"] == 2
        assert result["departments"] == {department_id: 1}
        assert _version(tenant_id, department_id, year, week) == 1
        assert _completion(group_a)["marked"] is True
        assert _completion(group_b)["marked"] is True


def test_bulk_write_success_multiple_departments_bumps_each_once(app_session) -> None:
    tenant_id = 3
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_a, group_a, _requirements_a = _seed_group("Bulk multi department site", "Bulk department A", group_label="Group A")
        _site_id, department_b, group_b, _requirements_b = _seed_group("Bulk multi department site", "Bulk department B", group_label="Group B")
        _seed_version(tenant_id, department_a, year, week, 0)
        _seed_version(tenant_id, department_b, year, week, 4)

        result = WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
            tenant_id=tenant_id,
            year=year,
            week=week,
            expected_base_versions={department_a: 0, department_b: 4},
            targets=[_target(department_a, group_a), _target(department_b, group_b)],
            marked=True,
        )

        assert result["departments"] == {department_a: 1, department_b: 5}
        assert _version(tenant_id, department_a, year, week) == 1
        assert _version(tenant_id, department_b, year, week) == 5
        assert _completion(group_a)["marked"] is True
        assert _completion(group_b)["marked"] is True


def test_bulk_write_mark_false_clears_exact_targets(app_session) -> None:
    tenant_id = 4
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_a, requirement_ids = _seed_group("Bulk clear site", "Bulk clear department", group_label="Group A")
        group_b = _create_group_in_department(department_id, requirement_ids, group_label="Group B")
        _seed_version(tenant_id, department_id, year, week, 0)
        service = WeekviewCohortBulkCompletionService()
        service.set_marked_many_with_weekview_versions(
            tenant_id=tenant_id,
            year=year,
            week=week,
            expected_base_versions={department_id: 0},
            targets=[_target(department_id, group_a), _target(department_id, group_b)],
            marked=True,
        )

        clear_result = service.set_marked_many_with_weekview_versions(
            tenant_id=tenant_id,
            year=year,
            week=week,
            expected_base_versions={department_id: 1},
            targets=[_target(department_id, group_a), _target(department_id, group_b)],
            marked=False,
        )

        assert clear_result["marked"] is False
        assert _completion(group_a)["marked"] is False
        assert _completion(group_b)["marked"] is False


def test_bulk_write_duplicate_exact_target_is_deduped(app_session) -> None:
    tenant_id = 5
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id, _requirements = _seed_group("Bulk dedupe site", "Bulk dedupe department")
        _seed_version(tenant_id, department_id, year, week, 0)

        result = WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
            tenant_id=tenant_id,
            year=year,
            week=week,
            expected_base_versions={department_id: 0},
            targets=[_target(department_id, group_id), _target(department_id, group_id)],
            marked=True,
        )

        assert result["target_count"] == 1
        assert _version(tenant_id, department_id, year, week) == 1
        assert _completion(group_id)["marked"] is True


def test_bulk_write_missing_expected_version_fails_before_mutation(app_session) -> None:
    tenant_id = 6
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id, _requirements = _seed_group("Bulk missing version site", "Bulk missing version department")
        _seed_version(tenant_id, department_id, year, week, 0)

        with pytest.raises(CohortBulkCompletionError, match="expected_base_versions_mismatch"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={},
                targets=[_target(department_id, group_id)],
                marked=True,
            )

        assert _version(tenant_id, department_id, year, week) == 0
        assert _completion(group_id) is None


def test_bulk_write_stale_first_department_has_zero_mutation(app_session) -> None:
    tenant_id = 7
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_a, group_a, _requirements_a = _seed_group("Bulk stale first site", "Bulk stale first A", group_label="Group A")
        _site_id, department_b, group_b, _requirements_b = _seed_group("Bulk stale first site", "Bulk stale first B", group_label="Group B")
        _seed_version(tenant_id, department_a, year, week, 1)
        _seed_version(tenant_id, department_b, year, week, 0)

        with pytest.raises(CohortWeekviewStaleError):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_a: 0, department_b: 0},
                targets=[_target(department_a, group_a), _target(department_b, group_b)],
                marked=True,
            )

        assert _version(tenant_id, department_a, year, week) == 1
        assert _version(tenant_id, department_b, year, week) == 0
        assert _completion(group_a) is None
        assert _completion(group_b) is None


def test_bulk_write_stale_later_department_rolls_back_earlier_version_bump(app_session) -> None:
    tenant_id = 8
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_a, group_a, _requirements_a = _seed_group("Bulk stale later site", "Bulk stale later A", group_label="Group A")
        _site_id, department_b, group_b, _requirements_b = _seed_group("Bulk stale later site", "Bulk stale later B", group_label="Group B")
        _seed_version(tenant_id, department_a, year, week, 0)
        _seed_version(tenant_id, department_b, year, week, 1)

        with pytest.raises(CohortWeekviewStaleError):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_a: 0, department_b: 0},
                targets=[_target(department_a, group_a), _target(department_b, group_b)],
                marked=True,
            )

        assert _version(tenant_id, department_a, year, week) == 0
        assert _version(tenant_id, department_b, year, week) == 1
        assert _completion(group_a) is None
        assert _completion(group_b) is None


def test_bulk_write_completion_failure_rolls_back_all_version_bumps(app_session, monkeypatch) -> None:
    tenant_id = 9
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_a, group_a, _requirements_a = _seed_group("Bulk rollback site", "Bulk rollback A", group_label="Group A")
        _site_id, department_b, group_b, _requirements_b = _seed_group("Bulk rollback site", "Bulk rollback B", group_label="Group B")
        _seed_version(tenant_id, department_a, year, week, 0)
        _seed_version(tenant_id, department_b, year, week, 0)

        original = DepartmentRequirementGroupCompletionRepo.set_marked_in_session
        calls: list[str] = []

        def _patched(self, db, department_id, group_id, service_date, meal_key, marked):
            calls.append(str(group_id))
            if len(calls) == 2:
                raise RuntimeError("completion failed")
            return original(self, db, department_id, group_id, service_date, meal_key, marked)

        monkeypatch.setattr(DepartmentRequirementGroupCompletionRepo, "set_marked_in_session", _patched)

        with pytest.raises(RuntimeError, match="completion failed"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_a: 0, department_b: 0},
                targets=[_target(department_a, group_a), _target(department_b, group_b)],
                marked=True,
            )

        assert _version(tenant_id, department_a, year, week) == 0
        assert _version(tenant_id, department_b, year, week) == 0
        assert _completion(group_a) is None
        assert _completion(group_b) is None


def test_bulk_write_rejects_invalid_meal_and_empty_targets(app_session) -> None:
    tenant_id = 10
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id, _requirements = _seed_group("Bulk validation site", "Bulk validation department")
        _seed_version(tenant_id, department_id, year, week, 0)

        with pytest.raises(CohortBulkCompletionError, match="meal_invalid"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_id: 0},
                targets=[_target(department_id, group_id, meal="breakfast")],
                marked=True,
            )

        with pytest.raises(CohortBulkCompletionError, match="targets_empty"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_id: 0},
                targets=[],
                marked=True,
            )

        assert _version(tenant_id, department_id, year, week) == 0
        assert _completion(group_id) is None


def test_bulk_write_rejects_service_date_outside_requested_week_before_mutation(app_session) -> None:
    tenant_id = 11
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id, _requirements = _seed_group("Bulk date site", "Bulk date department")
        _seed_version(tenant_id, department_id, year, week, 0)

        with pytest.raises(CohortBulkCompletionError, match="service_date_outside_requested_week"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_id: 0},
                targets=[_target(department_id, group_id, service_date=date(2026, 9, 28))],
                marked=True,
            )

        assert _version(tenant_id, department_id, year, week) == 0
        assert _completion(group_id) is None


def test_bulk_write_rejects_invalid_target_identity_before_mutation(app_session) -> None:
    tenant_id = 12
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id, _requirements = _seed_group("Bulk identity site", "Bulk identity department")
        _seed_version(tenant_id, department_id, year, week, 0)

        with pytest.raises(CohortBulkCompletionError, match="department_id_missing"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_id: 0},
                targets=[CohortBulkCompletionTarget(department_id="", group_id=group_id, service_date=date(2026, 9, 21), meal="lunch")],
                marked=True,
            )

        with pytest.raises(CohortBulkCompletionError, match="group_id_missing"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_id: 0},
                targets=[CohortBulkCompletionTarget(department_id=department_id, group_id="", service_date=date(2026, 9, 21), meal="lunch")],
                marked=True,
            )

        with pytest.raises(CohortBulkCompletionError, match="service_date_invalid"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_id: 0},
                targets=[CohortBulkCompletionTarget(department_id=department_id, group_id=group_id, service_date="2026-09-21", meal="lunch")],
                marked=True,
            )

        assert _version(tenant_id, department_id, year, week) == 0
        assert _completion(group_id) is None


def test_bulk_write_rejects_non_bool_marked_and_non_bool_validation_types(app_session) -> None:
    tenant_id = 13
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id, _requirements = _seed_group("Bulk bool site", "Bulk bool department")
        _seed_version(tenant_id, department_id, year, week, 0)

        with pytest.raises(CohortBulkCompletionError, match="marked_invalid"):
            WeekviewCohortBulkCompletionService().set_marked_many_with_weekview_versions(
                tenant_id=tenant_id,
                year=year,
                week=week,
                expected_base_versions={department_id: 0},
                targets=[_target(department_id, group_id)],
                marked=1,  # type: ignore[arg-type]
            )

        assert _version(tenant_id, department_id, year, week) == 0
        assert _completion(group_id) is None