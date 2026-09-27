from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from core.admin_repo import DepartmentsRepo, DietTypesRepo, SitesRepo
from core.department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from core.department_requirement_group_repo import DepartmentRequirementGroupsRepo
from core.db import get_session
from core.weekview.cohort_completion_service import CohortWeekviewStaleError, WeekviewCohortCompletionService
from core.weekview.repo import WeekviewRepo


def _seed_group(site_name: str, department_name: str, group_label: str = "Group") -> tuple[str, str, str]:
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
    return site["id"], department["id"], str(group["id"])


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


def _completion(group_id: str) -> dict[str, object] | None:
    return DepartmentRequirementGroupCompletionRepo().get(group_id, date(2026, 9, 21), "lunch")


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


def test_atomic_write_success_marks_completion_and_bumps_version(app_session) -> None:
    tenant_id = 1
    year = 2026
    week = 39

    with app_session.app_context():
        _site_id, department_id, group_id = _seed_group("Atomic success site", "Atomic success department")
        _seed_version(tenant_id, department_id, year, week, 0)
        _ensure_weekview_registrations_table()

        result = WeekviewCohortCompletionService().set_marked_with_weekview_version(
            tenant_id=tenant_id,
            department_id=department_id,
            year=year,
            week=week,
            expected_base_version=0,
            group_id=group_id,
            service_date="2026-09-21",
            meal="lunch",
            marked=True,
        )

        assert result["ok"] is True
        assert result["new_version"] == 1
        assert _version(tenant_id, department_id, year, week) == 1
        assert _completion(group_id)["marked"] is True
        db = get_session()
        try:
            assert int(db.execute(text("SELECT COUNT(*) FROM weekview_registrations")).scalar_one()) == 0
        finally:
            db.close()


def test_atomic_write_stale_expected_version_rejects_without_mutating(app_session) -> None:
    tenant_id = 2
    year = 2026
    week = 40

    with app_session.app_context():
        _site_id, department_id, group_id = _seed_group("Atomic stale site", "Atomic stale department")
        _seed_version(tenant_id, department_id, year, week, 1)

        with pytest.raises(CohortWeekviewStaleError):
            WeekviewCohortCompletionService().set_marked_with_weekview_version(
                tenant_id=tenant_id,
                department_id=department_id,
                year=year,
                week=week,
                expected_base_version=0,
                group_id=group_id,
                service_date="2026-09-21",
                meal="lunch",
                marked=True,
            )

        assert _version(tenant_id, department_id, year, week) == 1
        assert _completion(group_id) is None


def test_atomic_write_rolls_back_when_completion_fails_after_cas(app_session, monkeypatch) -> None:
    tenant_id = 3
    year = 2026
    week = 41

    with app_session.app_context():
        _site_id, department_id, group_id = _seed_group("Atomic rollback site", "Atomic rollback department")
        _seed_version(tenant_id, department_id, year, week, 0)

        def _boom(*args, **kwargs):
            raise RuntimeError("completion failed")

        monkeypatch.setattr(DepartmentRequirementGroupCompletionRepo, "set_marked_in_session", _boom)

        with pytest.raises(RuntimeError, match="completion failed"):
            WeekviewCohortCompletionService().set_marked_with_weekview_version(
                tenant_id=tenant_id,
                department_id=department_id,
                year=year,
                week=week,
                expected_base_version=0,
                group_id=group_id,
                service_date="2026-09-21",
                meal="lunch",
                marked=True,
            )

        assert _version(tenant_id, department_id, year, week) == 0
        assert _completion(group_id) is None


def test_atomic_write_clear_advances_version_and_marks_false(app_session) -> None:
    tenant_id = 4
    year = 2026
    week = 42

    with app_session.app_context():
        _site_id, department_id, group_id = _seed_group("Atomic clear site", "Atomic clear department")
        _seed_version(tenant_id, department_id, year, week, 0)

        service = WeekviewCohortCompletionService()
        first = service.set_marked_with_weekview_version(
            tenant_id=tenant_id,
            department_id=department_id,
            year=year,
            week=week,
            expected_base_version=0,
            group_id=group_id,
            service_date="2026-09-21",
            meal="lunch",
            marked=True,
        )
        second = service.set_marked_with_weekview_version(
            tenant_id=tenant_id,
            department_id=department_id,
            year=year,
            week=week,
            expected_base_version=int(first["new_version"]),
            group_id=group_id,
            service_date="2026-09-21",
            meal="lunch",
            marked=False,
        )

        assert int(first["new_version"]) == 1
        assert int(second["new_version"]) == 2
        assert _version(tenant_id, department_id, year, week) == 2
        assert _completion(group_id)["marked"] is False


def test_atomic_write_isolation_keeps_other_tuples_unchanged(app_session) -> None:
    tenant_id = 5
    year = 2026
    week = 43

    with app_session.app_context():
        _site_id, department_a, group_a = _seed_group("Atomic isolation site", "Atomic isolation department A", group_label="Group A")
        _site_id, department_b, group_b = _seed_group("Atomic isolation site", "Atomic isolation department B", group_label="Group B")
        _seed_version(tenant_id, department_a, year, week, 0)
        _seed_version(tenant_id, department_a, year, week + 1, 7)
        _seed_version(tenant_id, department_b, year, week, 4)

        WeekviewCohortCompletionService().set_marked_with_weekview_version(
            tenant_id=tenant_id,
            department_id=department_a,
            year=year,
            week=week,
            expected_base_version=0,
            group_id=group_a,
            service_date="2026-09-21",
            meal="lunch",
            marked=True,
        )

        assert _version(tenant_id, department_a, year, week) == 1
        assert _version(tenant_id, department_a, year, week + 1) == 7
        assert _version(tenant_id, department_b, year, week) == 4
        assert _completion(group_a)["marked"] is True
        assert _completion(group_b) is None
