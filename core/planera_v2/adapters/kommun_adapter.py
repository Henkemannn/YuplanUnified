from __future__ import annotations

from typing import Any

from ..domain import Deviation, PlanningSlice, UnitInput


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_category_keys(raw_categories: object) -> list[str]:
    if not isinstance(raw_categories, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in raw_categories:
        key = str(item).strip()
        if key and key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _requirement_form(raw_requirement: dict[str, Any]) -> str:
    for key in ("form", "texture", "consistency", "type"):
        value = str(raw_requirement.get(key) or "").strip()
        if value:
            return value
    return "unspecified"


def _project_requirement(raw_requirement: dict[str, Any], *, unit_id: str) -> Deviation | None:
    raw_categories = raw_requirement.get("category_keys")
    if not isinstance(raw_categories, list):
        raw_single_category = raw_requirement.get("category_key")
        if raw_single_category is not None:
            raw_categories = [raw_single_category]
    category_keys = _normalize_category_keys(raw_categories)
    quantity = _to_int(raw_requirement.get("quantity"), default=0)
    if quantity <= 0 or not category_keys:
        return None
    return Deviation(
        form=_requirement_form(raw_requirement),
        category_keys=category_keys,
        quantity=quantity,
        unit_id=unit_id,
    )


def _collect_unit_requirements(unit: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    raw_requirements = unit.get("requirements")
    raw_deviations = unit.get("deviations")
    if isinstance(raw_requirements, list):
        collected.extend(item for item in raw_requirements if isinstance(item, dict))
    if isinstance(raw_deviations, list):
        collected.extend(item for item in raw_deviations if isinstance(item, dict))
    return collected


def build_planning_slice_from_kommun_input(data: dict[str, Any]) -> PlanningSlice:
    raw_units = data.get("units")
    units = raw_units if isinstance(raw_units, list) else []

    if "baseline" in data:
        baseline = _to_int(data.get("baseline"), default=0)
    else:
        baseline = sum(_to_int(unit.get("baseline"), default=0) for unit in units if isinstance(unit, dict))

    raw_context = data.get("context")
    context: dict[str, object] = dict(raw_context) if isinstance(raw_context, dict) else {}
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

    unit_units: dict[str, UnitInput] = {}
    unit_deviations: dict[str, list[Deviation]] = {}
    warnings: list[str] = []

    for unit in units:
        if not isinstance(unit, dict):
            continue

        unit_id_raw = unit.get("unit_id")
        unit_id = str(unit_id_raw).strip() if unit_id_raw is not None else ""
        if not unit_id:
            continue

        baseline_total = _to_int(unit.get("baseline_total", unit.get("baseline")), default=0)
        unit_units[unit_id] = UnitInput(unit_id=unit_id, baseline_total=baseline_total)

        projected_deviations: list[Deviation] = []
        for raw_requirement in _collect_unit_requirements(unit):
            deviation = _project_requirement(raw_requirement, unit_id=unit_id)
            if deviation is not None:
                projected_deviations.append(deviation)

        if not projected_deviations and any(
            key in unit
            for key in (
                "aggregate_category_totals",
                "category_totals",
                "aggregate_requirements",
            )
        ):
            warnings.append(f"unit[{unit_id}] aggregate category totals cannot prove overlap; no deviations emitted")

        unit_deviations[unit_id] = projected_deviations

    ordered_unit_ids = sorted(unit_units.keys())
    ordered_units = tuple(unit_units[unit_id] for unit_id in ordered_unit_ids)
    ordered_deviations: list[Deviation] = []
    for unit_id in ordered_unit_ids:
        ordered_deviations.extend(unit_deviations.get(unit_id, []))

    compatibility_status = "ambiguous" if warnings else "resolved"
    if compatibility_status != "resolved":
        context["compatibility_status"] = compatibility_status
        context["compatibility_warnings"] = list(warnings)

    return PlanningSlice(
        baseline=baseline,
        units=ordered_units,
        deviations=tuple(ordered_deviations),
        context=context,
        warnings=tuple(warnings),
        compatibility_status=compatibility_status,
    )


def build_payload_from_kommun_input(data: dict[str, Any]) -> dict[str, Any]:
    planning_slice = build_planning_slice_from_kommun_input(data)
    return {
        "baseline": planning_slice.baseline,
        "units": [
            {"unit_id": unit.unit_id, "baseline_total": unit.baseline_total}
            for unit in planning_slice.units
        ],
        "deviations": [
            {
                "form": deviation.form,
                "category_keys": list(deviation.category_keys),
                "quantity": deviation.quantity,
                "unit_id": deviation.unit_id,
            }
            for deviation in planning_slice.deviations
        ],
        "context": {
            **planning_slice.context,
            **(
                {
                    "compatibility_status": planning_slice.compatibility_status,
                    "compatibility_warnings": list(planning_slice.warnings),
                }
                if planning_slice.compatibility_status != "resolved"
                else {}
            ),
        },
    }


__all__ = ["build_payload_from_kommun_input", "build_planning_slice_from_kommun_input"]
