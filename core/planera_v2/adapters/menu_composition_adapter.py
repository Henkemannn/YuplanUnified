from __future__ import annotations

from typing import Any


def _serialize_menu_metadata(menu: Any) -> dict[str, Any]:
    return {
        "menu_id": getattr(menu, "menu_id", None),
        "title": getattr(menu, "title", None),
        "site_id": getattr(menu, "site_id", None),
        "week_key": getattr(menu, "week_key", None),
        "version": getattr(menu, "version", None),
        "status": getattr(menu, "status", None),
    }


def _resolve_menu_row(*, detail: Any, composition_repository: Any) -> dict[str, Any]:
    ref_type = str(getattr(detail, "composition_ref_type", "") or "").strip().lower()
    row_payload = {
        "menu_detail": {
            "menu_detail_id": getattr(detail, "menu_detail_id", None),
            "menu_id": getattr(detail, "menu_id", None),
            "day": getattr(detail, "day", None),
            "meal_slot": getattr(detail, "meal_slot", None),
            "note": getattr(detail, "note", None),
            "sort_order": getattr(detail, "sort_order", 0),
        },
        "resolution": {
            "kind": "unresolved",
            "composition_ref_type": ref_type,
            "composition": None,
            "unresolved_text": getattr(detail, "unresolved_text", None),
        },
    }

    composition_id = str(getattr(detail, "composition_id", "") or "").strip()
    if ref_type == "composition" and composition_id:
        composition = composition_repository.get(composition_id)
        if composition is not None:
            row_payload["resolution"] = {
                "kind": "composition",
                "composition_ref_type": ref_type,
                "composition": {
                    "composition_id": composition.composition_id,
                    "composition_name": composition.composition_name,
                    "components": [
                        {
                            "component_id": item.component_id,
                            "component_name": item.component_name,
                            "role": item.role,
                            "sort_order": item.sort_order,
                        }
                        for item in composition.components
                    ],
                },
                "unresolved_text": None,
            }
        else:
            row_payload["resolution"] = {
                "kind": "unresolved",
                "composition_ref_type": ref_type,
                "composition": None,
                "unresolved_text": None,
                "warnings": ["composition_not_found"],
            }

    return row_payload


def build_menu_composition_payload(
    *,
    menu: Any,
    menu_details: list[Any],
    composition_repository: Any,
    menu_detail_id: str | None = None,
) -> dict[str, Any]:
    selected_detail_id = str(menu_detail_id or "").strip() or None

    filtered_details = list(menu_details)
    if selected_detail_id is not None:
        filtered_details = [
            detail
            for detail in menu_details
            if str(getattr(detail, "menu_detail_id", "") or "") == selected_detail_id
        ]

    rows = [
        _resolve_menu_row(detail=detail, composition_repository=composition_repository)
        for detail in filtered_details
    ]

    return {
        "menu": _serialize_menu_metadata(menu),
        "count": len(rows),
        "rows": rows,
    }


def build_menu_composition_grouped_payload(
    *,
    menu: Any,
    menu_details: list[Any],
    composition_repository: Any,
) -> dict[str, Any]:
    resolved_rows = [
        _resolve_menu_row(detail=detail, composition_repository=composition_repository)
        for detail in menu_details
    ]

    grouped_by_day: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in resolved_rows:
        detail = row.get("menu_detail") or {}
        day = str(detail.get("day") or "")
        meal_slot = str(detail.get("meal_slot") or "")
        grouped_by_day.setdefault(day, {}).setdefault(meal_slot, []).append(row)

    groups: list[dict[str, Any]] = []
    for day in sorted(grouped_by_day.keys()):
        meal_groups: list[dict[str, Any]] = []
        for meal_slot in sorted(grouped_by_day[day].keys()):
            rows = sorted(
                grouped_by_day[day][meal_slot],
                key=lambda item: int((item.get("menu_detail") or {}).get("sort_order") or 0),
            )
            meal_groups.append(
                {
                    "meal_slot": meal_slot,
                    "count": len(rows),
                    "rows": rows,
                }
            )
        groups.append(
            {
                "day": day,
                "count": sum(int(meal.get("count") or 0) for meal in meal_groups),
                "meals": meal_groups,
            }
        )

    return {
        "menu": _serialize_menu_metadata(menu),
        "count": len(resolved_rows),
        "days": groups,
    }
