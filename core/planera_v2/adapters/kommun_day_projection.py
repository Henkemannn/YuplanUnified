from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..domain import PlanRequest, PlanResult, UnitBreakdown, UnitInput
from ..shadow import ProductionShadowRun


@dataclass(frozen=True, slots=True)
class KommunDepartmentProjectionContext:
    department_id: str
    department_name: str


@dataclass(frozen=True, slots=True)
class RequirementGroupProjection:
    group_id: str
    diet_type_id: str
    diet_name: str


class KommunDayProjectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


def _normalize_id(value: object) -> str:
    return str(value or "").strip()


def _require_dict(value: object, *, code: str, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise KommunDayProjectionError(code, message)
    return value


def _require_meal_run(meal_key: str, meal_runs: Mapping[str, ProductionShadowRun]) -> ProductionShadowRun:
    run = meal_runs.get(meal_key)
    if run is None:
        raise KommunDayProjectionError("missing_meal_run", f"meal run missing for {meal_key}")
    if not run.acceptance.accepted:
        raise KommunDayProjectionError("blocked_meal_run", f"meal run blocked for {meal_key}")
    if run.diagnostic_result is None:
        raise KommunDayProjectionError("missing_diagnostic_result", f"diagnostic result missing for {meal_key}")
    return run


def _require_request_context(run: ProductionShadowRun) -> dict[str, Any]:
    context = _require_dict(run.request.context, code="missing_request_context", message="request context missing")
    return context


def _require_meal_label(meal_labels: Mapping[str, str], meal_key: str) -> str:
    label = _normalize_id(meal_labels.get(meal_key))
    if not label:
        raise KommunDayProjectionError("missing_meal_label", f"meal label missing for {meal_key}")
    return label


def _ordered_department_ids(departments: Sequence[KommunDepartmentProjectionContext]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for department in departments:
        department_id = _normalize_id(department.department_id)
        if not department_id:
            raise KommunDayProjectionError("unit_set_mismatch", "department id is blank")
        if department_id in seen:
            raise KommunDayProjectionError("unit_set_mismatch", "duplicate department id in projection context")
        seen.add(department_id)
        ordered.append(department_id)
    return ordered


def _index_units(run: ProductionShadowRun) -> dict[str, UnitInput]:
    units: dict[str, UnitInput] = {}
    for unit in run.request.units:
        unit_id = _normalize_id(unit.unit_id)
        if not unit_id:
            raise KommunDayProjectionError("unit_set_mismatch", "blank unit id in canonical request")
        if unit_id in units:
            raise KommunDayProjectionError("unit_set_mismatch", f"duplicate unit id in canonical request: {unit_id}")
        units[unit_id] = unit
    return units


def _index_breakdowns(run: ProductionShadowRun) -> dict[str, UnitBreakdown]:
    breakdowns = dict(run.diagnostic_result.per_unit_breakdown)
    return breakdowns


def _group_projection_lookup(
    requirement_projection_by_group_id: Mapping[str, RequirementGroupProjection],
) -> dict[str, RequirementGroupProjection]:
    lookup: dict[str, RequirementGroupProjection] = {}
    for group_id, projection in requirement_projection_by_group_id.items():
        normalized_group_id = _normalize_id(group_id)
        if not normalized_group_id:
            raise KommunDayProjectionError("missing_group_projection", "projection group id is blank")
        if normalized_group_id in lookup:
            raise KommunDayProjectionError("missing_group_projection", f"duplicate projection mapping for group {normalized_group_id}")
        if not isinstance(projection, RequirementGroupProjection):
            raise KommunDayProjectionError("missing_group_projection", f"invalid projection metadata for group {normalized_group_id}")
        if _normalize_id(projection.group_id) != normalized_group_id:
            raise KommunDayProjectionError("missing_group_projection", f"projection metadata group id mismatch for {normalized_group_id}")
        if not _normalize_id(projection.diet_type_id):
            raise KommunDayProjectionError("missing_group_projection", f"projection diet_type_id missing for group {normalized_group_id}")
        if not _normalize_id(projection.diet_name):
            raise KommunDayProjectionError("missing_group_projection", f"projection diet_name missing for group {normalized_group_id}")
        lookup[normalized_group_id] = projection
    return lookup


def _require_group_refs(context: Mapping[str, object]) -> list[dict[str, Any]]:
    raw_refs = context.get("requirement_group_refs")
    if raw_refs is None:
        return []
    if not isinstance(raw_refs, list):
        raise KommunDayProjectionError("missing_group_projection", "requirement_group_refs must be a list")
    refs: list[dict[str, Any]] = []
    for raw_ref in raw_refs:
        ref = _require_dict(raw_ref, code="missing_group_projection", message="requirement_group_ref must be a mapping")
        refs.append(ref)
    return refs


def _project_meal(
    *,
    meal_key: str,
    run: ProductionShadowRun,
    departments: Sequence[KommunDepartmentProjectionContext],
    requirement_projection_by_group_id: Mapping[str, RequirementGroupProjection],
    site_id: str,
    service_date: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    context = _require_request_context(run)
    request_units = _index_units(run)
    breakdowns = _index_breakdowns(run)
    ordered_department_ids = _ordered_department_ids(departments)

    if _normalize_id(context.get("site_id")) != _normalize_id(site_id):
        raise KommunDayProjectionError("unit_set_mismatch", f"canonical request site_id mismatch for {meal_key}")
    if _normalize_id(context.get("date")) != _normalize_id(service_date):
        raise KommunDayProjectionError("unit_set_mismatch", f"canonical request date mismatch for {meal_key}")
    if _normalize_id(context.get("meal_key")) != _normalize_id(meal_key):
        raise KommunDayProjectionError("unit_set_mismatch", f"canonical request meal_key mismatch for {meal_key}")

    request_unit_ids = set(request_units.keys())
    department_ids = set(ordered_department_ids)
    if request_unit_ids != department_ids:
        raise KommunDayProjectionError("unit_set_mismatch", "canonical request units do not match supplied departments")

    group_projection_lookup = _group_projection_lookup(requirement_projection_by_group_id)
    group_refs = _require_group_refs(context)

    refs_by_unit: dict[str, list[dict[str, Any]]] = {department_id: [] for department_id in ordered_department_ids}
    for ref in group_refs:
        ref_unit_id = _normalize_id(ref.get("unit_id"))
        ref_group_id = _normalize_id(ref.get("group_id"))
        quantity = int(ref.get("quantity") or 0)
        if quantity <= 0:
            continue
        if ref_unit_id not in department_ids:
            raise KommunDayProjectionError("unit_set_mismatch", f"group ref unit not in supplied departments: {ref_unit_id}")
        if ref_group_id not in group_projection_lookup:
            raise KommunDayProjectionError("missing_group_projection", f"missing projection metadata for group {ref_group_id}")
        refs_by_unit[ref_unit_id].append(ref)

    meal_rows: list[dict[str, Any]] = []
    totals_by_compat_id: dict[str, dict[str, Any]] = {}
    projected_meal_special_total = 0
    projected_baseline_total = 0
    projected_normal_total = 0

    for department in departments:
        unit_id = _normalize_id(department.department_id)
        unit = request_units[unit_id]
        breakdown = breakdowns.get(unit_id)
        if breakdown is None:
            raise KommunDayProjectionError("unit_set_mismatch", f"missing diagnostic breakdown for unit {unit_id}")

        baseline_total = int(unit.baseline_total)
        deviation_total = int(breakdown.deviation_total)
        normal_total = int(breakdown.normal_total)
        projected_baseline_total += baseline_total
        projected_normal_total += normal_total

        projected_rows: dict[str, dict[str, Any]] = {}
        projected_quantity_total = 0
        for ref in refs_by_unit.get(unit_id, []):
            group_id = _normalize_id(ref.get("group_id"))
            quantity = int(ref.get("quantity") or 0)
            if quantity <= 0:
                continue
            projection = group_projection_lookup.get(group_id)
            if projection is None:
                raise KommunDayProjectionError("missing_group_projection", f"missing projection metadata for group {group_id}")
            compat_id = _normalize_id(projection.diet_type_id)
            compat_name = _normalize_id(projection.diet_name)
            if not compat_id or not compat_name:
                raise KommunDayProjectionError("missing_group_projection", f"incomplete projection metadata for group {group_id}")

            existing = projected_rows.get(compat_id)
            if existing is None:
                projected_rows[compat_id] = {
                    "diet_type_id": compat_id,
                    "diet_name": compat_name,
                    "count": quantity,
                }
            else:
                if existing["diet_name"] != compat_name:
                    raise KommunDayProjectionError("projection_label_conflict", f"conflicting labels for compatibility id {compat_id}")
                existing["count"] = int(existing["count"]) + quantity
            projected_quantity_total += quantity

        if projected_quantity_total != deviation_total:
            raise KommunDayProjectionError(
                "projection_quantity_mismatch",
                f"projected quantity {projected_quantity_total} does not match canonical deviation total {deviation_total} for unit {unit_id}",
            )

        meal_rows.append(
            {
                "department_id": unit_id,
                "department_name": department.department_name,
                "meals": {
                    meal_key: {
                        "residents_total": baseline_total,
                        "special_diets": sorted(projected_rows.values(), key=lambda row: (str(row["diet_type_id"]), str(row["diet_name"]))),
                        "normal_diet_count": normal_total,
                    }
                },
            }
        )

        for row in projected_rows.values():
            compat_id = str(row["diet_type_id"])
            compat_name = str(row["diet_name"])
            entry = totals_by_compat_id.get(compat_id)
            if entry is None:
                totals_by_compat_id[compat_id] = {"diet_type_id": compat_id, "diet_name": compat_name, "count": int(row["count"]) }
            else:
                if entry["diet_name"] != compat_name:
                    raise KommunDayProjectionError("projection_label_conflict", f"conflicting labels for compatibility id {compat_id}")
                entry["count"] = int(entry["count"]) + int(row["count"])
            projected_meal_special_total += int(row["count"])

    if projected_meal_special_total != int(run.diagnostic_result.totals.deviation_total):
        raise KommunDayProjectionError(
            "projection_quantity_mismatch",
            f"projected meal total {projected_meal_special_total} does not match canonical total {int(run.diagnostic_result.totals.deviation_total)} for {meal_key}",
        )
    if projected_baseline_total != int(run.diagnostic_result.totals.baseline_total):
        raise KommunDayProjectionError(
            "projection_quantity_mismatch",
            f"projected baseline total {projected_baseline_total} does not match canonical total {int(run.diagnostic_result.totals.baseline_total)} for {meal_key}",
        )
    if projected_normal_total != int(run.diagnostic_result.totals.normal_total):
        raise KommunDayProjectionError(
            "projection_quantity_mismatch",
            f"projected normal total {projected_normal_total} does not match canonical total {int(run.diagnostic_result.totals.normal_total)} for {meal_key}",
        )

    return (
        {
            "residents_total": int(run.diagnostic_result.totals.baseline_total),
            "special_diets": sorted(totals_by_compat_id.values(), key=lambda row: (str(row["diet_type_id"]), str(row["diet_name"]))),
            "normal_diet_count": int(run.diagnostic_result.totals.normal_total),
        },
        meal_rows,
    )


def project_canonical_kommun_day(
    *,
    site_id: str,
    site_name: str,
    service_date: str,
    meal_labels: Mapping[str, str],
    departments: Sequence[KommunDepartmentProjectionContext],
    meal_runs: Mapping[str, ProductionShadowRun],
    requirement_projection_by_group_id: Mapping[str, RequirementGroupProjection],
) -> dict[str, object]:
    normalized_site_id = _normalize_id(site_id)
    normalized_site_name = str(site_name)
    normalized_service_date = str(service_date)
    normalized_labels = {
        "lunch": _require_meal_label(meal_labels, "lunch"),
        "dinner": _require_meal_label(meal_labels, "dinner"),
    }

    lunch_run = _require_meal_run("lunch", meal_runs)
    dinner_run = _require_meal_run("dinner", meal_runs)

    lunch_context = _require_request_context(lunch_run)
    dinner_context = _require_request_context(dinner_run)
    if _normalize_id(lunch_context.get("meal_key")) != "lunch":
        raise KommunDayProjectionError("missing_meal_run", "lunch run meal_key mismatch")
    if _normalize_id(dinner_context.get("meal_key")) != "dinner":
        raise KommunDayProjectionError("missing_meal_run", "dinner run meal_key mismatch")

    lunch_totals, lunch_department_rows = _project_meal(
        meal_key="lunch",
        run=lunch_run,
        departments=departments,
        requirement_projection_by_group_id=requirement_projection_by_group_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date,
    )
    dinner_totals, dinner_department_rows = _project_meal(
        meal_key="dinner",
        run=dinner_run,
        departments=departments,
        requirement_projection_by_group_id=requirement_projection_by_group_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date,
    )

    department_rows: list[dict[str, Any]] = []
    for index, department in enumerate(departments):
        lunch_row = lunch_department_rows[index]["meals"]["lunch"]
        dinner_row = dinner_department_rows[index]["meals"]["dinner"]
        department_rows.append(
            {
                "department_id": _normalize_id(department.department_id),
                "department_name": department.department_name,
                "meals": {
                    "lunch": lunch_row,
                    "dinner": dinner_row,
                },
            }
        )

    return {
        "site_id": normalized_site_id,
        "site_name": normalized_site_name,
        "date": normalized_service_date,
        "meal_labels": normalized_labels,
        "departments": department_rows,
        "totals": {
            "lunch": lunch_totals,
            "dinner": dinner_totals,
        },
    }


__all__ = [
    "KommunDayProjectionError",
    "KommunDepartmentProjectionContext",
    "RequirementGroupProjection",
    "project_canonical_kommun_day",
]