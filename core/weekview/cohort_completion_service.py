from __future__ import annotations

from datetime import date as _date

from ..db import get_new_session
from ..department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from .repo import WeekviewRepo


class CohortWeekviewStaleError(RuntimeError):
    pass


class WeekviewCohortCompletionService:
    def __init__(self, *, weekview_repo: WeekviewRepo | None = None, completion_repo: DepartmentRequirementGroupCompletionRepo | None = None) -> None:
        self._weekview_repo = weekview_repo or WeekviewRepo()
        self._completion_repo = completion_repo or DepartmentRequirementGroupCompletionRepo()

    def set_marked_with_weekview_version(
        self,
        *,
        tenant_id: int | str,
        department_id: str,
        year: int,
        week: int,
        expected_base_version: int,
        group_id: str,
        service_date: str | _date,
        meal: str,
        marked: bool,
    ) -> dict[str, object]:
        db = get_new_session()
        try:
            new_version = self._weekview_repo.compare_and_bump_version_in_session(
                db,
                tenant_id=tenant_id,
                year=year,
                week=week,
                department_id=department_id,
                expected_version=expected_base_version,
            )
            if new_version is None:
                db.rollback()
                raise CohortWeekviewStaleError("weekview_version_stale")
            completion = self._completion_repo.set_marked_in_session(
                db,
                department_id=department_id,
                group_id=group_id,
                service_date=service_date,
                meal_key=meal,
                marked=marked,
            )
            db.commit()
            return {"ok": True, "new_version": new_version, "completion": completion}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


__all__ = ["CohortWeekviewStaleError", "WeekviewCohortCompletionService"]