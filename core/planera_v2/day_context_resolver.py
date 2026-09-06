from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from sqlalchemy import text

from ..admin_repo import DepartmentsRepo
from ..db import get_session, get_site_tenant
from ..department_requirement_group_repo import DepartmentRequirementGroupsRepo
from ..weekview.service import resolve_effective_resident_counts_for_day
from .day_orchestration import (
    KommunDayBusinessContext,
    KommunDepartmentProjectionContext,
    KommunGroupCompatibilityMetadata,
)


class KommunDayContextResolverError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


def _normalize_id(value: object) -> str:
    return str(value or "").strip()


def _normalize_service_date(value: object) -> date:
    if isinstance(value, date):
        return value
    raw = _normalize_id(value)
    if not raw:
        raise KommunDayContextResolverError("service_date_missing", "service_date is required")
    try:
        return date.fromisoformat(raw)
    except Exception as exc:
        raise KommunDayContextResolverError("service_date_invalid", "service_date must be ISO format") from exc


def _require_meal_labels(meal_labels: Mapping[str, str]) -> dict[str, str]:
    lunch = _normalize_id(meal_labels.get("lunch"))
    dinner = _normalize_id(meal_labels.get("dinner"))
    if not lunch:
        raise KommunDayContextResolverError("missing_meal_label", "lunch label missing")
    if not dinner:
        raise KommunDayContextResolverError("missing_meal_label", "dinner label missing")
    return {"lunch": lunch, "dinner": dinner}


def _require_owned_site(tenant_id: int | str, site_id: str) -> None:
    site_tenant_id = get_site_tenant(site_id)
    if site_tenant_id is None:
        raise KommunDayContextResolverError("site_not_owned", "site ownership could not be resolved")
    if int(site_tenant_id) != int(tenant_id):
        raise KommunDayContextResolverError("site_not_owned", "site does not belong to tenant")


def _resolve_site_name(site_id: str) -> str:
    db = get_session()
    try:
        row = db.execute(text("SELECT name FROM sites WHERE id=:site_id"), {"site_id": site_id}).fetchone()
        if not row:
            raise KommunDayContextResolverError("site_not_found", "site not found")
        site_name = _normalize_id(row[0])
        if not site_name:
            raise KommunDayContextResolverError("site_name_missing", "site name missing")
        return site_name
    finally:
        db.close()


def _resolve_departments(site_id: str, department_id: str | None) -> tuple[KommunDepartmentProjectionContext, ...]:
    departments = DepartmentsRepo().list_for_site(site_id)
    if department_id:
        selected = [row for row in departments if _normalize_id(row.get("id")) == department_id]
        if not selected:
            raise KommunDayContextResolverError("department_scope_mismatch", "requested department is not part of the site")
        departments = selected
    return tuple(
        KommunDepartmentProjectionContext(
            department_id=_normalize_id(row.get("id")),
            department_name=_normalize_id(row.get("name")),
        )
        for row in departments
    )


def _resolve_explicit_day_counts(
    *,
    tenant_id: int | str,
    department_id: str,
    service_date: date,
) -> dict[str, int]:
    year, week, _weekday = service_date.isocalendar()
    db = get_session()
    try:
        rows = db.execute(
            text(
                """
                SELECT meal, count
                FROM weekview_residents_count
                WHERE tenant_id=:tenant_id AND department_id=:department_id AND year=:year AND week=:week AND day_of_week=:day_of_week
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "department_id": department_id,
                "year": year,
                "week": week,
                "day_of_week": _weekday,
            },
        ).fetchall()
    except Exception:
        rows = []
    finally:
        db.close()
    return {str(row[0]): int(row[1] or 0) for row in rows if _normalize_id(row[0]) in {"lunch", "dinner"}}


def _resolve_requirement_metadata(
    *,
    service_date: date,
    departments: tuple[KommunDepartmentProjectionContext, ...],
) -> dict[str, KommunGroupCompatibilityMetadata]:
    mapping: dict[str, KommunGroupCompatibilityMetadata] = {}
    group_repo = DepartmentRequirementGroupsRepo()
    for department in departments:
        for group in group_repo.list_for_department(department.department_id):
            group_id = _normalize_id(group.get("id"))
            if not group_id:
                continue
            label = _normalize_id(group.get("label"))
            if not label:
                continue
            mapping[group_id] = KommunGroupCompatibilityMetadata(group_id=group_id, diet_name=label)
    return mapping


def _resolve_day_baselines(
    *,
    tenant_id: int | str,
    service_date: date,
    departments: tuple[KommunDepartmentProjectionContext, ...],
) -> tuple[dict[str, int], dict[str, int]]:
    year, week, weekday = service_date.isocalendar()
    lunch_baselines: dict[str, int] = {}
    dinner_baselines: dict[str, int] = {}
    for department in departments:
        explicit_counts = _resolve_explicit_day_counts(
            tenant_id=tenant_id,
            department_id=department.department_id,
            service_date=service_date,
        )
        resolved = resolve_effective_resident_counts_for_day(department.department_id, year, week, weekday)
        lunch_baselines[department.department_id] = int(explicit_counts["lunch"]) if "lunch" in explicit_counts else int(resolved["lunch"])
        dinner_baselines[department.department_id] = int(explicit_counts["dinner"]) if "dinner" in explicit_counts else int(resolved["dinner"])
    return lunch_baselines, dinner_baselines


def resolve_kommun_day_business_context(
    *,
    tenant_id: int | str,
    site_id: str,
    service_date,
    meal_labels: Mapping[str, str],
    department_id: str | None = None,
) -> KommunDayBusinessContext:
    normalized_site_id = _normalize_id(site_id)
    if not normalized_site_id:
        raise KommunDayContextResolverError("site_id_missing", "site_id is required")
    normalized_department_id = _normalize_id(department_id) or None
    service_date_value = _normalize_service_date(service_date)
    labels = _require_meal_labels(meal_labels)

    _require_owned_site(tenant_id, normalized_site_id)
    site_name = _resolve_site_name(normalized_site_id)
    departments = _resolve_departments(normalized_site_id, normalized_department_id)
    lunch_baselines, dinner_baselines = _resolve_day_baselines(
        tenant_id=tenant_id,
        service_date=service_date_value,
        departments=departments,
    )
    requirement_projection_by_group_id = _resolve_requirement_metadata(
        service_date=service_date_value,
        departments=departments,
    )

    return KommunDayBusinessContext(
        tenant_id=tenant_id,
        site_id=normalized_site_id,
        site_name=site_name,
        service_date=service_date_value.isoformat(),
        departments=departments,
        meal_labels=labels,
        lunch_baselines=lunch_baselines,
        dinner_baselines=dinner_baselines,
        requirement_projection_by_group_id=requirement_projection_by_group_id,
    )


__all__ = [
    "KommunDayBusinessContext",
    "KommunDayContextResolverError",
    "KommunDepartmentProjectionContext",
    "KommunGroupCompatibilityMetadata",
    "resolve_kommun_day_business_context",
]