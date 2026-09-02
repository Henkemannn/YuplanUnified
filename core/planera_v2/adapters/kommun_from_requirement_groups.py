from __future__ import annotations

from datetime import date as _date, datetime as _datetime
from typing import Any

from sqlalchemy import text

from ...db import get_session
from ...department_requirement_group_service_overrides_repo import (
    resolve_effective_quantity_in_session,
)
from ..domain import Deviation, PlanningSlice, UnitInput


def _normalize_service_date(value: object) -> _date:
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


def _normalize_meal_key(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        raise ValueError("meal_key_empty")
    return raw


def _normalize_unit_id(value: object) -> str:
    unit_id = str(value or "").strip()
    if not unit_id:
        raise ValueError("unit_id_empty")
    return unit_id


def _normalize_baseline(value: object) -> int:
    baseline = int(value)
    if baseline < 0:
        raise ValueError("baseline_negative")
    return baseline


def _sorted_unique_requirement_keys(keys: list[str]) -> list[str]:
    normalized = [str(key).strip() for key in keys if str(key).strip()]
    if len(normalized) != len(set(normalized)):
        raise ValueError("duplicate_requirement_key")
    return sorted(normalized)


def _load_department_site_id(db, unit_id: str, site_id: str) -> str:
    row = db.execute(
        text("SELECT id, site_id FROM departments WHERE id=:id"),
        {"id": unit_id},
    ).fetchone()
    if row is None:
        raise ValueError("department_not_found")
    department_site_id = str(row[1] or "").strip()
    if not department_site_id:
        raise ValueError("department_site_missing")
    if department_site_id != site_id:
        raise ValueError("department_site_mismatch")
    return department_site_id


def _load_group_rows(db, unit_id: str) -> list[tuple[str, int, int]]:
    rows = db.execute(
        text(
            """
            SELECT id, default_quantity, is_active
            FROM department_requirement_groups
            WHERE department_id = :department_id
            ORDER BY id ASC
            """
        ),
        {"department_id": unit_id},
    ).fetchall()
    return [(str(row[0]), int(row[1] or 0), int(row[2] or 0)) for row in rows]


def _load_group_requirement_keys(db, group_id: str, department_site_id: str) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT dt.id, dt.requirement_key, dt.semantics, dt.site_id
            FROM department_requirement_group_requirements gr
            JOIN dietary_types dt ON dt.id = gr.dietary_type_id
            WHERE gr.group_id = :group_id
            ORDER BY dt.requirement_key ASC, dt.id ASC
            """
        ),
        {"group_id": group_id},
    ).fetchall()
    if not rows:
        raise ValueError("department_requirement_group_requirements_missing")

    requirement_keys: list[str] = []
    for row in rows:
        requirement_site_id = str(row[3] or "").strip()
        if not requirement_site_id:
            raise ValueError("dietary_type_site_missing")
        if requirement_site_id != department_site_id:
            raise ValueError("dietary_type_site_mismatch")

        requirement_key = str(row[1] or "").strip()
        if not requirement_key:
            raise ValueError("dietary_type_requirement_key_missing")

        semantics = str(row[2] or "").strip().lower()
        if semantics != "atomic":
            raise ValueError("dietary_type_not_atomic")

        requirement_keys.append(requirement_key)

    return _sorted_unique_requirement_keys(requirement_keys)


def build_planning_slice_from_requirement_groups(
    *,
    site_id: str,
    service_date,
    meal_key,
    unit_baselines: dict[str, object],
    context: dict[str, Any] | None = None,
) -> PlanningSlice:
    normalized_site_id = str(site_id or "").strip()
    if not normalized_site_id:
        raise ValueError("site_id_empty")

    normalized_service_date = _normalize_service_date(service_date)
    normalized_meal_key = _normalize_meal_key(meal_key)

    caller_context = dict(context) if isinstance(context, dict) else {}
    warnings: list[str] = []
    units: list[UnitInput] = []
    deviations: list[Deviation] = []
    requirement_group_refs: list[dict[str, object]] = []

    db = get_session()
    try:
        unit_items: list[tuple[str, int]] = []
        for raw_unit_id, raw_baseline in unit_baselines.items():
            unit_id = _normalize_unit_id(raw_unit_id)
            baseline_total = _normalize_baseline(raw_baseline)
            _load_department_site_id(db, unit_id, normalized_site_id)
            unit_items.append((unit_id, baseline_total))

        for unit_id, baseline_total in sorted(unit_items, key=lambda item: item[0]):
            units.append(UnitInput(unit_id=unit_id, baseline_total=baseline_total))
            group_rows = _load_group_rows(db, unit_id)

            effective_quantity_total = 0
            group_payloads: list[tuple[str, list[str], int]] = []

            for group_id, default_quantity, is_active in group_rows:
                requirement_keys = _load_group_requirement_keys(db, group_id, normalized_site_id)
                effective_quantity = resolve_effective_quantity_in_session(
                    db,
                    group_id,
                    default_quantity,
                    is_active,
                    normalized_service_date,
                    normalized_meal_key,
                )

                if effective_quantity <= 0:
                    continue

                group_payloads.append((group_id, requirement_keys, effective_quantity))
                effective_quantity_total += effective_quantity

            if effective_quantity_total > baseline_total:
                warnings.append(f"unit[{unit_id}] canonical deviations exceed baseline")

            for group_id, requirement_keys, effective_quantity in sorted(
                group_payloads,
                key=lambda item: (
                    tuple(item[1]),
                    str(item[0]),
                ),
            ):
                deviations.append(
                    Deviation(
                        form="unspecified",
                        category_keys=list(requirement_keys),
                        quantity=effective_quantity,
                        unit_id=unit_id,
                    )
                )
                requirement_group_refs.append(
                    {
                        "group_id": group_id,
                        "unit_id": unit_id,
                        "category_keys": list(requirement_keys),
                        "quantity": effective_quantity,
                    }
                )

        planning_context = dict(caller_context)
        planning_context.pop("compatibility_warnings", None)
        planning_context["source"] = "canonical_requirement_groups"
        planning_context["site_id"] = normalized_site_id
        planning_context["date"] = normalized_service_date.isoformat()
        planning_context["meal_key"] = normalized_meal_key
        planning_context["compatibility_source_precision"] = "canonical_atomic_groups"
        planning_context["compatibility_status"] = "resolved"
        planning_context["requirement_group_refs"] = requirement_group_refs
        if warnings:
            planning_context["compatibility_warnings"] = list(warnings)

        return PlanningSlice(
            baseline=sum(baseline_total for _, baseline_total in unit_items),
            units=tuple(units),
            deviations=tuple(deviations),
            context=planning_context,
            warnings=tuple(warnings),
            compatibility_status="resolved",
        )
    finally:
        db.close()


__all__ = ["build_planning_slice_from_requirement_groups"]