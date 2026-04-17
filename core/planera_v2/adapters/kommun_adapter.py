from __future__ import annotations

from typing import Any


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_payload_from_kommun_input(data: dict[str, Any]) -> dict[str, Any]:
    raw_units = data.get("units")
    units = raw_units if isinstance(raw_units, list) else []

    if "baseline" in data:
        baseline = _to_int(data.get("baseline"), default=0)
    else:
        baseline = sum(_to_int(unit.get("baseline"), default=0) for unit in units if isinstance(unit, dict))

    deviations: list[dict[str, Any]] = []
    payload_units: list[dict[str, Any]] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue

        unit_id_raw = unit.get("unit_id")
        unit_id = str(unit_id_raw) if unit_id_raw is not None else None

        if unit_id is not None and str(unit_id).strip():
            payload_units.append(
                {
                    "unit_id": str(unit_id).strip(),
                    "baseline_total": _to_int(unit.get("baseline"), default=0),
                }
            )

        raw_unit_deviations = unit.get("deviations")
        unit_deviations = raw_unit_deviations if isinstance(raw_unit_deviations, list) else []

        for raw_dev in unit_deviations:
            if not isinstance(raw_dev, dict):
                continue

            raw_categories = raw_dev.get("category_keys")
            category_keys = [str(item) for item in raw_categories] if isinstance(raw_categories, list) else []

            deviations.append(
                {
                    "form": str(raw_dev.get("form") or ""),
                    "category_keys": category_keys,
                    "quantity": _to_int(raw_dev.get("quantity"), default=0),
                    "unit_id": unit_id,
                }
            )

    raw_context = data.get("context")
    context = dict(raw_context) if isinstance(raw_context, dict) else {}
    if "meal_key" in data and "meal_key" not in context:
        context["meal_key"] = data.get("meal_key")

    component_id = str(data.get("component_id") or "").strip()
    if component_id:
        context["component_id"] = component_id

    component_name = str(data.get("component_name") or "").strip()
    if component_name:
        context["component_name"] = component_name

    component_role = str(data.get("component_role") or "").strip()
    if component_role:
        context["component_role"] = component_role

    component_mode = str(data.get("component_mode") or "").strip()
    if component_mode:
        context["component_mode"] = component_mode
    elif component_id:
        context["component_mode"] = "informational"

    return {
        "baseline": baseline,
        "units": payload_units,
        "deviations": deviations,
        "context": context,
    }
