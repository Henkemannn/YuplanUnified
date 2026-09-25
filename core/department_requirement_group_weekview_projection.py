from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, datetime as _datetime
from typing import Any

from sqlalchemy import text

from .db import get_session, get_site_tenant
from .department_requirement_group_completion_repo import DepartmentRequirementGroupCompletionRepo
from .department_requirement_group_quantity_resolver import resolve_effective_quantity
from .department_requirement_group_repo import DepartmentRequirementGroupsRepo
from .admin_repo import DietTypesRepo


def _normalize_service_date(value: Any) -> _date:
    if isinstance(value, _datetime):
        raise ValueError("service_date_invalid")
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("service_date_invalid")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:
        raise ValueError("service_date_invalid") from exc


def _normalize_meal_key(value: Any) -> str:
    meal_key = str(value or "").strip().lower()
    if meal_key not in {"lunch", "dinner"}:
        raise ValueError("meal_key_invalid")
    return meal_key


def _normalize_id(value: Any) -> str:
    return str(value or "").strip()


def _resolve_label(requirement_id: int, *, label_by_id: dict[int, str], fallback_name: str, fallback_key: str | None) -> str:
    label = label_by_id.get(int(requirement_id), "").strip()
    if label:
        return label
    fallback_name = str(fallback_name or "").strip()
    if fallback_name:
        return fallback_name
    fallback_key = str(fallback_key or "").strip()
    if fallback_key:
        return fallback_key
    return str(requirement_id)


def _join_labels(labels: tuple[str, ...]) -> str:
    return " + ".join([label for label in labels if str(label).strip()])


@dataclass(frozen=True, slots=True)
class DepartmentRequirementGroupWeekviewNeedVM:
    group_id: str
    department_id: str
    service_date: str
    meal_key: str
    display_label: str
    group_label: str | None
    primary_requirement_id: int | None
    primary_label: str | None
    modifier_requirement_ids: tuple[int, ...]
    modifier_labels: tuple[str, ...]
    member_requirement_ids: tuple[int, ...]
    member_labels: tuple[str, ...]
    effective_quantity: int
    marked: bool
    unresolved_primary: bool


@dataclass(frozen=True, slots=True)
class DepartmentRequirementGroupWeekviewProjectionVM:
    department_id: str
    service_date: str
    meal_key: str
    needs: tuple[DepartmentRequirementGroupWeekviewNeedVM, ...]


def build_department_requirement_group_weekview_projection(
    *,
    tenant_id: int | None,
    site_id: str,
    department_id: str,
    service_date: Any,
    meal_key: Any,
) -> DepartmentRequirementGroupWeekviewProjectionVM:
    normalized_site_id = _normalize_id(site_id)
    if not normalized_site_id:
        raise ValueError("site_id_empty")
    normalized_department_id = _normalize_id(department_id)
    if not normalized_department_id:
        raise ValueError("department_id_empty")
    normalized_service_date = _normalize_service_date(service_date)
    normalized_meal_key = _normalize_meal_key(meal_key)

    db = get_session()
    try:
        row = db.execute(
            text("SELECT site_id FROM departments WHERE id=:id"),
            {"id": normalized_department_id},
        ).fetchone()
        if row is None:
            raise ValueError("department_not_found")
        department_site_id = _normalize_id(row[0])
        if department_site_id != normalized_site_id:
            raise ValueError("department_site_mismatch")
        if tenant_id is not None:
            resolved_tenant_id = get_site_tenant(normalized_site_id)
            if resolved_tenant_id is not None and int(resolved_tenant_id) != int(tenant_id):
                raise ValueError("site_not_owned")
    finally:
        db.close()

    group_repo = DepartmentRequirementGroupsRepo()
    group_rows = group_repo.list_for_department(normalized_department_id)
    diet_types = DietTypesRepo().list_all(site_id=normalized_site_id)
    label_by_id: dict[int, str] = {int(row["id"]): str(row.get("name") or "") for row in diet_types if str(row.get("id") or "").strip()}

    completion_repo = DepartmentRequirementGroupCompletionRepo()
    needs: list[DepartmentRequirementGroupWeekviewNeedVM] = []
    for group in group_rows:
        group_id = _normalize_id(group.get("id"))
        if not group_id:
            continue
        requirements = group.get("requirements") or []
        member_ids: list[int] = []
        member_labels: list[str] = []
        primary_requirement_id = group.get("primary_requirement_id")
        primary_label = None

        for requirement in requirements:
            requirement_id = int(requirement.get("dietary_type_id") or 0)
            if requirement_id <= 0:
                continue
            member_ids.append(requirement_id)
            member_labels.append(
                _resolve_label(
                    requirement_id,
                    label_by_id=label_by_id,
                    fallback_name=str(requirement.get("name") or ""),
                    fallback_key=str(requirement.get("requirement_key") or "") or None,
                )
            )

        if primary_requirement_id is not None:
            primary_requirement_id_int = int(primary_requirement_id)
            primary_label = _resolve_label(
                primary_requirement_id_int,
                label_by_id=label_by_id,
                fallback_name=next((str(req.get("name") or "") for req in requirements if int(req.get("dietary_type_id") or 0) == primary_requirement_id_int), ""),
                fallback_key=next((str(req.get("requirement_key") or "") for req in requirements if int(req.get("dietary_type_id") or 0) == primary_requirement_id_int), "") or None,
            )
            modifier_ids = tuple(req_id for req_id in member_ids if req_id != primary_requirement_id_int)
            modifier_labels = tuple(label for req_id, label in zip(member_ids, member_labels) if req_id != primary_requirement_id_int)
            display_label = str(group.get("label") or "").strip() or _join_labels((primary_label,) + modifier_labels)
            unresolved_primary = False
        else:
            primary_requirement_id_int = None
            modifier_ids = tuple()
            modifier_labels = tuple()
            display_label = _join_labels(tuple(member_labels)) or str(group.get("label") or "").strip() or group_id
            unresolved_primary = True

        effective_quantity = int(resolve_effective_quantity(group_id, normalized_service_date, normalized_meal_key))
        if effective_quantity <= 0:
            continue

        completion = completion_repo.get(group_id, normalized_service_date, normalized_meal_key)
        needs.append(
            DepartmentRequirementGroupWeekviewNeedVM(
                group_id=group_id,
                department_id=normalized_department_id,
                service_date=normalized_service_date.isoformat(),
                meal_key=normalized_meal_key,
                display_label=display_label,
                group_label=str(group.get("label") or "").strip() or None,
                primary_requirement_id=primary_requirement_id_int,
                primary_label=primary_label,
                modifier_requirement_ids=modifier_ids,
                modifier_labels=modifier_labels,
                member_requirement_ids=tuple(member_ids),
                member_labels=tuple(member_labels),
                effective_quantity=effective_quantity,
                marked=bool(completion.get("marked")) if completion is not None else False,
                unresolved_primary=unresolved_primary,
            )
        )

    return DepartmentRequirementGroupWeekviewProjectionVM(
        department_id=normalized_department_id,
        service_date=normalized_service_date.isoformat(),
        meal_key=normalized_meal_key,
        needs=tuple(needs),
    )


__all__ = [
    "DepartmentRequirementGroupWeekviewNeedVM",
    "DepartmentRequirementGroupWeekviewProjectionVM",
    "build_department_requirement_group_weekview_projection",
]