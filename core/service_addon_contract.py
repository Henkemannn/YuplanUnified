from __future__ import annotations

from typing import Any, Mapping

SERVICE_ADDON_SERVICE_SCOPES: tuple[str, ...] = ("all_services", "lunch", "dinner")
SERVICE_ADDON_QUANTITY_MODES: tuple[str, ...] = ("whole_department", "custom")


def normalize_service_addon_scope(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw not in SERVICE_ADDON_SERVICE_SCOPES:
        raise ValueError("service_addon_scope_invalid")
    return raw


def normalize_service_addon_quantity_mode(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw not in SERVICE_ADDON_QUANTITY_MODES:
        raise ValueError("service_addon_quantity_mode_invalid")
    return raw


def _normalize_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except Exception:
        raise ValueError("service_addon_count_invalid")


def infer_service_addon_scope(lunch_count: Any, dinner_count: Any) -> str | None:
    lunch_i = _normalize_count(lunch_count)
    dinner_i = _normalize_count(dinner_count)
    has_lunch = lunch_i is not None and lunch_i > 0
    has_dinner = dinner_i is not None and dinner_i > 0
    if has_lunch and has_dinner:
        return "all_services"
    if has_lunch:
        return "lunch"
    if has_dinner:
        return "dinner"
    return None


def canonicalize_service_addon_assignment(
    *,
    service_scope: str | None = None,
    quantity_mode: str | None = None,
    lunch_count: Any = None,
    dinner_count: Any = None,
) -> dict[str, Any]:
    scope = normalize_service_addon_scope(service_scope)
    mode = normalize_service_addon_quantity_mode(quantity_mode)
    lunch_i = _normalize_count(lunch_count)
    dinner_i = _normalize_count(dinner_count)
    has_lunch = lunch_i is not None and lunch_i > 0
    has_dinner = dinner_i is not None and dinner_i > 0

    if mode is None:
        mode = "custom"

    if mode == "whole_department":
        if has_lunch or has_dinner:
            raise ValueError("service_addon_whole_department_counts_must_be_null")
        if scope is None:
            scope = "all_services"
        return {
            "service_scope": scope,
            "quantity_mode": mode,
            "lunch_count": None,
            "dinner_count": None,
        }

    inferred_scope = scope or infer_service_addon_scope(lunch_i, dinner_i)
    if inferred_scope is None:
        raise ValueError("service_addon_counts_required")

    if inferred_scope == "lunch":
        if not has_lunch:
            raise ValueError("service_addon_lunch_count_required")
        if has_dinner:
            raise ValueError("service_addon_dinner_count_must_be_null")
        dinner_i = None
    elif inferred_scope == "dinner":
        if not has_dinner:
            raise ValueError("service_addon_dinner_count_required")
        if has_lunch:
            raise ValueError("service_addon_lunch_count_must_be_null")
        lunch_i = None
    elif inferred_scope == "all_services":
        if not (has_lunch and has_dinner):
            raise ValueError("service_addon_all_services_counts_required")
    else:
        raise ValueError("service_addon_scope_invalid")

    return {
        "service_scope": inferred_scope,
        "quantity_mode": mode,
        "lunch_count": lunch_i if has_lunch else None,
        "dinner_count": dinner_i if has_dinner else None,
    }


def resolve_service_addon_quantity(
    assignment: Mapping[str, Any],
    *,
    meal: str,
    year: int | None = None,
    week: int | None = None,
    weekday: int | None = None,
) -> int:
    meal_key = str(meal or "").strip().lower()
    if meal_key not in {"lunch", "dinner"}:
        return 0

    scope = normalize_service_addon_scope(assignment.get("service_scope"))
    mode = normalize_service_addon_quantity_mode(assignment.get("quantity_mode")) or "custom"

    if scope == "lunch" and meal_key != "lunch":
        return 0
    if scope == "dinner" and meal_key != "dinner":
        return 0

    if mode == "whole_department":
        department_id = str(assignment.get("department_id") or "").strip()
        if not department_id:
            raise ValueError("service_addon_department_required_for_resolution")
        if year is None or week is None or weekday is None:
            raise ValueError("service_addon_resolution_context_required")
        from .weekview.service import resolve_effective_resident_counts_for_day

        eff = resolve_effective_resident_counts_for_day(department_id, int(year), int(week), int(weekday))
        return int(eff.get(meal_key, 0) or 0)

    if scope == "lunch":
        return int(assignment.get("lunch_count") or 0)
    if scope == "dinner":
        return int(assignment.get("dinner_count") or 0)
    if scope == "all_services":
        if meal_key == "lunch":
            return int(assignment.get("lunch_count") or 0)
        return int(assignment.get("dinner_count") or 0)

    raise ValueError("service_addon_scope_invalid")
