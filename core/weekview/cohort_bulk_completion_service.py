from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, datetime as _datetime

from ..db import get_new_session
from ..department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from .cohort_completion_service import CohortWeekviewStaleError
from .repo import WeekviewRepo


class CohortBulkCompletionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CohortBulkCompletionTarget:
    department_id: str
    group_id: str
    service_date: _date
    meal: str


@dataclass(frozen=True, slots=True)
class CohortBulkCompletionResult:
    marked: bool
    target_count: int
    departments: dict[str, int]


class WeekviewCohortBulkCompletionService:
    def __init__(self, *, weekview_repo: WeekviewRepo | None = None, completion_repo: DepartmentRequirementGroupCompletionRepo | None = None) -> None:
        self._weekview_repo = weekview_repo or WeekviewRepo()
        self._completion_repo = completion_repo or DepartmentRequirementGroupCompletionRepo()

    def _normalize_service_date(self, value: object) -> _date:
        if isinstance(value, _datetime):
            raise CohortBulkCompletionError("service_date_invalid")
        if isinstance(value, _date):
            return value
        raise CohortBulkCompletionError("service_date_invalid")

    def _normalize_meal(self, value: object) -> str:
        meal = str(value or "").strip().lower()
        if meal not in {"lunch", "dinner"}:
            raise CohortBulkCompletionError("meal_invalid")
        return meal

    def _normalize_target(self, target: object) -> CohortBulkCompletionTarget:
        if not isinstance(target, CohortBulkCompletionTarget):
            raise CohortBulkCompletionError("target_invalid")
        department_id = str(target.department_id or "").strip()
        group_id = str(target.group_id or "").strip()
        if not department_id:
            raise CohortBulkCompletionError("department_id_missing")
        if not group_id:
            raise CohortBulkCompletionError("group_id_missing")
        service_date = self._normalize_service_date(target.service_date)
        meal = self._normalize_meal(target.meal)
        iso_year, iso_week, _ = service_date.isocalendar()
        return CohortBulkCompletionTarget(
            department_id=department_id,
            group_id=group_id,
            service_date=service_date,
            meal=meal,
        )

    def _normalize_expected_base_versions(self, expected_base_versions: object) -> dict[str, int]:
        if not isinstance(expected_base_versions, dict):
            raise CohortBulkCompletionError("expected_base_versions_invalid")
        normalized: dict[str, int] = {}
        for raw_department_id, raw_version in expected_base_versions.items():
            department_id = str(raw_department_id or "").strip()
            if not department_id:
                raise CohortBulkCompletionError("department_id_missing")
            try:
                version = int(raw_version)
            except Exception as exc:
                raise CohortBulkCompletionError(f"expected_base_version_invalid:{department_id}") from exc
            normalized[department_id] = version
        return normalized

    def set_marked_many_with_weekview_versions(
        self,
        *,
        tenant_id: int | str,
        year: int,
        week: int,
        expected_base_versions: object,
        targets: object,
        marked: bool,
    ) -> dict[str, object]:
        if not isinstance(marked, bool):
            raise CohortBulkCompletionError("marked_invalid")

        raw_targets = list(targets or []) if isinstance(targets, (list, tuple, set)) else list(targets or [])
        if not raw_targets:
            raise CohortBulkCompletionError("targets_empty")

        normalized_targets: list[CohortBulkCompletionTarget] = []
        for target in raw_targets:
            normalized = self._normalize_target(target)
            iso_year, iso_week, _ = normalized.service_date.isocalendar()
            if int(iso_year) != int(year) or int(iso_week) != int(week):
                raise CohortBulkCompletionError("service_date_outside_requested_week")
            normalized_targets.append(normalized)

        deduped_targets: dict[tuple[str, str, _date, str], CohortBulkCompletionTarget] = {}
        for target in normalized_targets:
            key = (target.department_id, target.group_id, target.service_date, target.meal)
            deduped_targets.setdefault(key, target)

        unique_targets = tuple(deduped_targets.values())
        if not unique_targets:
            raise CohortBulkCompletionError("targets_empty")

        affected_departments = sorted({target.department_id for target in unique_targets})
        normalized_expected_base_versions = self._normalize_expected_base_versions(expected_base_versions)
        if set(normalized_expected_base_versions) != set(affected_departments):
            raise CohortBulkCompletionError("expected_base_versions_mismatch")

        targets_by_department: dict[str, list[CohortBulkCompletionTarget]] = {department_id: [] for department_id in affected_departments}
        for target in unique_targets:
            targets_by_department[target.department_id].append(target)
        for department_id in targets_by_department:
            targets_by_department[department_id].sort(key=lambda item: (item.service_date.isoformat(), item.meal, item.group_id))

        db = get_new_session()
        department_versions: dict[str, int] = {}
        try:
            for department_id in affected_departments:
                new_version = self._weekview_repo.compare_and_bump_version_in_session(
                    db,
                    tenant_id=tenant_id,
                    year=year,
                    week=week,
                    department_id=department_id,
                    expected_version=normalized_expected_base_versions[department_id],
                )
                if new_version is None:
                    db.rollback()
                    raise CohortWeekviewStaleError("weekview_version_stale")
                department_versions[department_id] = int(new_version)

            for department_id in affected_departments:
                for target in targets_by_department[department_id]:
                    self._completion_repo.set_marked_in_session(
                        db,
                        department_id=department_id,
                        group_id=target.group_id,
                        service_date=target.service_date,
                        meal_key=target.meal,
                        marked=marked,
                    )

            db.commit()
            return {
                "marked": marked,
                "target_count": len(unique_targets),
                "departments": department_versions,
            }
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


__all__ = [
    "CohortBulkCompletionError",
    "CohortBulkCompletionResult",
    "CohortBulkCompletionTarget",
    "WeekviewCohortBulkCompletionService",
]