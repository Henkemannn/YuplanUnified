from __future__ import annotations

from typing import Any


_ADAPTER_VERSION = "menu-composition-adapter/v1.2"


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


def _build_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    total_rows = len(rows)
    resolved_rows = 0
    unresolved_rows = 0
    rows_with_roles = 0
    rows_missing_roles = 0

    for row in rows:
        resolution = row.get("resolution") or {}
        kind = str(resolution.get("kind") or "").strip().lower()
        if kind != "composition":
            unresolved_rows += 1
            continue

        resolved_rows += 1
        composition = resolution.get("composition") or {}
        components = composition.get("components") or []

        if not components:
            rows_missing_roles += 1
            continue

        has_missing_role = any(not str(item.get("role") or "").strip() for item in components)
        if has_missing_role:
            rows_missing_roles += 1
        else:
            rows_with_roles += 1

    return {
        "total_rows": total_rows,
        "resolved_rows": resolved_rows,
        "unresolved_rows": unresolved_rows,
        "rows_with_roles": rows_with_roles,
        "rows_missing_roles": rows_missing_roles,
    }


def _ordered_resolved_rows(
    *,
    menu_details: list[Any],
    composition_repository: Any,
) -> list[dict[str, Any]]:
    indexed_rows = [
        {
            "row": _resolve_menu_row(detail=detail, composition_repository=composition_repository),
            "insertion_index": index,
        }
        for index, detail in enumerate(menu_details)
    ]
    return sorted(
        indexed_rows,
        key=lambda item: (
            int(((item.get("row") or {}).get("menu_detail") or {}).get("sort_order") or 0),
            int(item.get("insertion_index") or 0),
            str((((item.get("row") or {}).get("menu_detail") or {}).get("menu_detail_id") or "")),
        ),
    )


def _build_role_groups(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for index, component in enumerate(components):
        role_value = str(component.get("role") or "").strip()
        role_key = role_value if role_value else ""
        if role_key not in grouped:
            grouped[role_key] = {
                "role": role_value or None,
                "components": [],
                "_first_index": index,
            }
            order.append(role_key)
        grouped[role_key]["components"].append(component)

    role_groups: list[dict[str, Any]] = []
    for role_key in order:
        group = grouped[role_key]
        role_groups.append(
            {
                "role": group["role"],
                "components": sorted(
                    list(group["components"]),
                    key=lambda item: (
                        int(item.get("sort_order") or 0),
                        str(item.get("component_id") or ""),
                    ),
                ),
                "_first_index": int(group.get("_first_index") or 0),
            }
        )

    ordered = sorted(
        role_groups,
        key=lambda group: (
            int(group.get("_first_index") or 0),
            str(group.get("role") or ""),
        ),
    )
    cleaned: list[dict[str, Any]] = []
    for group in ordered:
        clean = dict(group)
        clean.pop("_first_index", None)
        cleaned.append(clean)
    return cleaned


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
        "adapter_version": _ADAPTER_VERSION,
        "menu": _serialize_menu_metadata(menu),
        "count": len(rows),
        "readiness": _build_readiness_summary(rows),
        "rows": rows,
    }


def build_menu_composition_grouped_payload(
    *,
    menu: Any,
    menu_details: list[Any],
    composition_repository: Any,
) -> dict[str, Any]:
    ordered_rows = _ordered_resolved_rows(
        menu_details=menu_details,
        composition_repository=composition_repository,
    )

    groups_by_day: dict[str, dict[str, Any]] = {}
    day_order: list[str] = []
    for item in ordered_rows:
        row = item.get("row") or {}
        detail = row.get("menu_detail") or {}
        day = str(detail.get("day") or "")
        meal_slot = str(detail.get("meal_slot") or "")

        if day not in groups_by_day:
            groups_by_day[day] = {
                "day": day,
                "count": 0,
                "meals_by_slot": {},
                "meal_order": [],
                "first_sort_order": int(detail.get("sort_order") or 0),
                "first_insertion_index": int(item.get("insertion_index") or 0),
            }
            day_order.append(day)

        day_group = groups_by_day[day]
        meals_by_slot = day_group["meals_by_slot"]
        meal_order = day_group["meal_order"]

        if meal_slot not in meals_by_slot:
            meals_by_slot[meal_slot] = {
                "meal_slot": meal_slot,
                "count": 0,
                "rows": [],
                "first_sort_order": int(detail.get("sort_order") or 0),
                "first_insertion_index": int(item.get("insertion_index") or 0),
            }
            meal_order.append(meal_slot)

        meal_group = meals_by_slot[meal_slot]
        meal_group["rows"].append(row)
        meal_group["count"] = int(meal_group["count"] or 0) + 1
        day_group["count"] = int(day_group["count"] or 0) + 1

    groups: list[dict[str, Any]] = []
    for day in day_order:
        day_group = groups_by_day[day]
        meals: list[dict[str, Any]] = []
        for meal_slot in day_group["meal_order"]:
            meal_group = day_group["meals_by_slot"][meal_slot]
            meals.append(
                {
                    "meal_slot": meal_group["meal_slot"],
                    "count": meal_group["count"],
                    "rows": meal_group["rows"],
                    "_first_sort_order": meal_group["first_sort_order"],
                    "_first_insertion_index": meal_group["first_insertion_index"],
                }
            )

        ordered_meals = sorted(
            meals,
            key=lambda meal: (
                int(meal.get("_first_sort_order") or 0),
                int(meal.get("_first_insertion_index") or 0),
                str(meal.get("meal_slot") or ""),
            ),
        )
        cleaned_meals: list[dict[str, Any]] = []
        for meal in ordered_meals:
            cleaned = dict(meal)
            cleaned.pop("_first_sort_order", None)
            cleaned.pop("_first_insertion_index", None)
            cleaned_meals.append(cleaned)

        groups.append(
            {
                "day": day_group["day"],
                "count": day_group["count"],
                "meals": cleaned_meals,
                "_first_sort_order": day_group["first_sort_order"],
                "_first_insertion_index": day_group["first_insertion_index"],
            }
        )

    ordered_groups = sorted(
        groups,
        key=lambda group: (
            int(group.get("_first_sort_order") or 0),
            int(group.get("_first_insertion_index") or 0),
            str(group.get("day") or ""),
        ),
    )

    cleaned_groups: list[dict[str, Any]] = []
    for group in ordered_groups:
        cleaned = dict(group)
        cleaned.pop("_first_sort_order", None)
        cleaned.pop("_first_insertion_index", None)
        cleaned_groups.append(cleaned)

    resolved_rows = [item.get("row") or {} for item in ordered_rows]

    return {
        "adapter_version": _ADAPTER_VERSION,
        "menu": _serialize_menu_metadata(menu),
        "count": len(ordered_rows),
        "readiness": _build_readiness_summary(resolved_rows),
        "days": cleaned_groups,
    }


def build_menu_composition_production_shape_payload(
    *,
    menu: Any,
    menu_details: list[Any],
    composition_repository: Any,
) -> dict[str, Any]:
    ordered_rows = _ordered_resolved_rows(
        menu_details=menu_details,
        composition_repository=composition_repository,
    )

    blocks_by_context: dict[tuple[str, str], dict[str, Any]] = {}
    context_order: list[tuple[str, str]] = []

    for item in ordered_rows:
        row = item.get("row") or {}
        detail = row.get("menu_detail") or {}
        resolution = row.get("resolution") or {}

        day = str(detail.get("day") or "")
        meal_slot = str(detail.get("meal_slot") or "")
        context_key = (day, meal_slot)
        if context_key not in blocks_by_context:
            blocks_by_context[context_key] = {
                "context": {
                    "day": day,
                    "meal_slot": meal_slot,
                },
                "compositions": [],
                "unresolved_rows": [],
                "_first_sort_order": int(detail.get("sort_order") or 0),
                "_first_insertion_index": int(item.get("insertion_index") or 0),
            }
            context_order.append(context_key)

        block = blocks_by_context[context_key]
        kind = str(resolution.get("kind") or "").strip().lower()
        if kind == "composition":
            composition = resolution.get("composition") or {}
            components = list(composition.get("components") or [])
            block["compositions"].append(
                {
                    "menu_detail": {
                        "menu_detail_id": detail.get("menu_detail_id"),
                        "note": detail.get("note"),
                        "sort_order": detail.get("sort_order"),
                    },
                    "composition": {
                        "composition_id": composition.get("composition_id"),
                        "composition_name": composition.get("composition_name"),
                        "components": components,
                        "role_groups": _build_role_groups(components),
                    },
                }
            )
        else:
            block["unresolved_rows"].append(
                {
                    "menu_detail": {
                        "menu_detail_id": detail.get("menu_detail_id"),
                        "note": detail.get("note"),
                        "sort_order": detail.get("sort_order"),
                    },
                    "unresolved_text": resolution.get("unresolved_text"),
                    "warnings": list(resolution.get("warnings") or []),
                }
            )

    blocks: list[dict[str, Any]] = []
    for context_key in context_order:
        blocks.append(blocks_by_context[context_key])

    ordered_blocks = sorted(
        blocks,
        key=lambda block: (
            int(block.get("_first_sort_order") or 0),
            int(block.get("_first_insertion_index") or 0),
            str((block.get("context") or {}).get("day") or ""),
            str((block.get("context") or {}).get("meal_slot") or ""),
        ),
    )

    cleaned_blocks: list[dict[str, Any]] = []
    for block in ordered_blocks:
        cleaned = dict(block)
        cleaned.pop("_first_sort_order", None)
        cleaned.pop("_first_insertion_index", None)
        cleaned_blocks.append(cleaned)

    return {
        "adapter_version": "menu-composition-adapter/v1.3-production-shape",
        "menu": _serialize_menu_metadata(menu),
        "readiness": _build_readiness_summary([item.get("row") or {} for item in ordered_rows]),
        "context_blocks": cleaned_blocks,
    }
