from __future__ import annotations

from datetime import date as _date
from typing import Any

from .department_requirement_group_repo import DepartmentRequirementGroupsRepo
from .department_requirement_group_weekview_projection import build_department_requirement_group_weekview_projection


def _day_lookup(days: list[dict[str, Any]] | None) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for idx, day in enumerate(days or [], start=1):
        try:
            dow = int(day.get("day_of_week") or idx)
        except Exception:
            dow = idx
        if 1 <= dow <= 7:
            lookup[dow] = day
    return lookup


def _iso_date_for_day(year: int, week: int, dow: int) -> str:
    return _date.fromisocalendar(year, week, dow).isoformat()


def _legacy_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows or []:
        row_copy = dict(row)
        row_copy.setdefault("row_kind", "legacy")
        row_copy.setdefault("row_label", row_copy.get("diet_type_name") or row_copy.get("kosttyp_name") or "")
        out.append(row_copy)
    return out


def build_week_grid_specialkost_rows(
    *,
    tenant_id: int | None,
    site_id: str,
    department_id: str,
    year: int,
    week: int,
    days: list[dict[str, Any]] | None,
    legacy_rows: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return the existing week-grid row contract for either legacy or cohort data.

    If the department has registered requirement groups, cohort rows replace the legacy rows.
    Otherwise the legacy rows are returned unchanged except for a harmless row_kind marker.
    """

    group_rows = DepartmentRequirementGroupsRepo().list_for_department(department_id)
    if not group_rows:
        return _legacy_rows(legacy_rows)

    day_lookup = _day_lookup(days)
    projection_cache: dict[tuple[int, str], dict[str, Any]] = {}
    for dow in range(1, 8):
        day = day_lookup.get(dow) or {}
        service_date = str(day.get("date") or "").strip() or _iso_date_for_day(year, week, dow)
        for meal_key in ("lunch", "dinner"):
            try:
                projection = build_department_requirement_group_weekview_projection(
                    tenant_id=tenant_id,
                    site_id=site_id,
                    department_id=department_id,
                    service_date=service_date,
                    meal_key=meal_key,
                )
            except Exception:
                projection = None
            projection_cache[(dow, meal_key)] = {
                need.group_id: need for need in (projection.needs if projection else ())
            }

    rows: list[dict[str, Any]] = []
    for group in group_rows:
        group_id = str(group.get("id") or "").strip()
        if not group_id:
            continue

        row_label = ""
        cells: list[dict[str, Any]] = []
        has_positive = False

        for dow in range(1, 8):
            day = day_lookup.get(dow) or {}
            lunch_alt2 = bool(day.get("alt2_lunch"))
            for meal_key in ("lunch", "dinner"):
                need = projection_cache.get((dow, meal_key), {}).get(group_id)
                count = int(need.effective_quantity) if need is not None else 0
                is_done = bool(need.marked) if need is not None else False
                if count > 0:
                    has_positive = True
                    if not row_label:
                        row_label = str(need.display_label or "").strip()
                cells.append(
                    {
                        "day_index": dow,
                        "meal": meal_key,
                        "count": count,
                        "is_done": is_done,
                        "is_override": False,
                        "is_alt2": lunch_alt2 if meal_key == "lunch" else False,
                        "group_id": group_id,
                        "row_kind": "cohort",
                    }
                )

        if not has_positive:
            continue

        if not row_label:
            row_label = str(group.get("label") or "").strip() or group_id

        rows.append(
            {
                "row_kind": "cohort",
                "group_id": group_id,
                "row_label": row_label,
                "diet_type_name": row_label,
                "diet_type_id": None,
                "cells": cells,
            }
        )

    return rows


__all__ = ["build_week_grid_specialkost_rows"]