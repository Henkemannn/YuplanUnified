from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from sqlalchemy import text

from ..db import get_session
from ..planera_service import PlaneraService
from .dev_runner import PlaneraV2DevRun, run_planera_v2_from_current_day


@dataclass(frozen=True)
class PlaneraDaySummary:
    unit_ids: list[str]
    unit_baselines: dict[str, int]
    unit_special_deviations: dict[str, dict[str, int]]
    totals: dict[str, int]


@dataclass(frozen=True)
class PlaneraComparison:
    context: dict[str, object]
    current: PlaneraDaySummary
    v2: PlaneraDaySummary
    matches: dict[str, bool]
    mismatches: list[str]
    caveats: list[str]


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_departments_for_site(site_id: str) -> list[tuple[str, str]]:
    db = get_session()
    try:
        rows = db.execute(
            text("SELECT id, name FROM departments WHERE site_id=:site_id ORDER BY name, id"),
            {"site_id": site_id},
        ).fetchall()
    finally:
        db.close()

    out: list[tuple[str, str]] = []
    for row in rows:
        dep_id = str(row[0] or "").strip()
        dep_name = str(row[1] or "")
        if dep_id:
            out.append((dep_id, dep_name))
    return out


def _summarize_current_day(day_payload: dict[str, Any], meal_key: str) -> PlaneraDaySummary:
    unit_baselines: dict[str, int] = {}
    unit_special_deviations: dict[str, dict[str, int]] = {}

    departments = day_payload.get("departments") if isinstance(day_payload.get("departments"), list) else []

    for dep in departments:
        if not isinstance(dep, dict):
            continue
        unit_id = str(dep.get("department_id") or "").strip()
        if not unit_id:
            continue

        meals = dep.get("meals") if isinstance(dep.get("meals"), dict) else {}
        meal_data = meals.get(meal_key) if isinstance(meals.get(meal_key), dict) else {}

        residents_total = _to_int(meal_data.get("residents_total"), default=0)
        if residents_total < 0:
            residents_total = 0
        unit_baselines[unit_id] = residents_total

        category_map: dict[str, int] = {}
        special_diets = meal_data.get("special_diets") if isinstance(meal_data.get("special_diets"), list) else []
        for item in special_diets:
            if not isinstance(item, dict):
                continue
            category_key = str(item.get("diet_type_id") or item.get("diet_name") or "").strip()
            quantity = _to_int(item.get("count"), default=0)
            if not category_key or quantity <= 0:
                continue
            category_map[category_key] = category_map.get(category_key, 0) + quantity

        unit_special_deviations[unit_id] = dict(sorted(category_map.items()))

    total_baseline = sum(unit_baselines.values())
    total_deviations = sum(sum(cats.values()) for cats in unit_special_deviations.values())
    total_normal = max(0, total_baseline - total_deviations)

    return PlaneraDaySummary(
        unit_ids=sorted(unit_baselines.keys()),
        unit_baselines=dict(sorted(unit_baselines.items())),
        unit_special_deviations=dict(sorted(unit_special_deviations.items())),
        totals={
            "baseline_total": total_baseline,
            "deviation_total": total_deviations,
            "normal_total": total_normal,
        },
    )


def _summarize_v2(run: PlaneraV2DevRun) -> PlaneraDaySummary:
    unit_baselines: dict[str, int] = {unit.unit_id: int(unit.baseline_total) for unit in run.request.units}

    unit_special_deviations: dict[str, dict[str, int]] = {}
    for deviation in run.request.deviations:
        unit_id = str(deviation.unit_id or "").strip()
        if not unit_id:
            continue
        if not deviation.category_keys:
            continue
        category_key = str(deviation.category_keys[0] or "").strip()
        if not category_key:
            continue
        bucket = unit_special_deviations.setdefault(unit_id, {})
        bucket[category_key] = bucket.get(category_key, 0) + int(deviation.quantity)

    for unit_id in list(unit_special_deviations.keys()):
        unit_special_deviations[unit_id] = dict(sorted(unit_special_deviations[unit_id].items()))

    return PlaneraDaySummary(
        unit_ids=sorted(unit_baselines.keys()),
        unit_baselines=dict(sorted(unit_baselines.items())),
        unit_special_deviations=dict(sorted(unit_special_deviations.items())),
        totals={
            "baseline_total": int(run.result.totals.baseline_total),
            "deviation_total": int(run.result.totals.deviation_total),
            "normal_total": int(run.result.totals.normal_total),
        },
    )


def compare_current_planera_vs_v2_day(
    tenant_id: int | str,
    site_id: str,
    iso_date: str,
    meal_key: str,
    *,
    planera_service: PlaneraService | None = None,
    departments: Iterable[tuple[str, str]] | None = None,
    dev_runner: Callable[..., PlaneraV2DevRun] = run_planera_v2_from_current_day,
) -> PlaneraComparison:
    svc = planera_service or PlaneraService()
    dep_list = list(departments) if departments is not None else _resolve_departments_for_site(site_id)

    day_payload = svc.compute_day(
        tenant_id=tenant_id,
        site_id=site_id,
        iso_date=iso_date,
        departments=dep_list,
    )
    if not isinstance(day_payload, dict):
        day_payload = {}

    current_summary = _summarize_current_day(day_payload, meal_key)

    run = dev_runner(
        tenant_id=tenant_id,
        site_id=site_id,
        iso_date=iso_date,
        meal_key=meal_key,
        planera_service=svc,
        departments=dep_list,
    )
    v2_summary = _summarize_v2(run)

    matches = {
        "context": bool(run.request.context.get("site_id") == site_id and run.request.context.get("date") == iso_date),
        "unit_list": current_summary.unit_ids == v2_summary.unit_ids,
        "unit_baselines": current_summary.unit_baselines == v2_summary.unit_baselines,
        "unit_special_deviations": current_summary.unit_special_deviations == v2_summary.unit_special_deviations,
        "total_baseline": current_summary.totals["baseline_total"] == v2_summary.totals["baseline_total"],
        "total_deviations": current_summary.totals["deviation_total"] == v2_summary.totals["deviation_total"],
        "total_normal": current_summary.totals["normal_total"] == v2_summary.totals["normal_total"],
    }

    mismatches: list[str] = []
    if not matches["unit_list"]:
        mismatches.append("Unit list differs between current Planera and Planera 2.0 run.")
    if not matches["unit_baselines"]:
        mismatches.append("Unit baselines differ.")
    if not matches["unit_special_deviations"]:
        mismatches.append("Effective unit special deviations differ.")
    if not matches["total_baseline"]:
        mismatches.append("Total baseline differs.")
    if not matches["total_deviations"]:
        mismatches.append("Total deviations differs.")
    if not matches["total_normal"]:
        mismatches.append("Total normal differs.")

    caveats = [
        "Form semantics are currently adapter fallback labels and are not authoritative for parity.",
        "Comparison is strongest on totals, unit baselines, and effective unit deviations.",
    ]

    return PlaneraComparison(
        context={
            "site_id": site_id,
            "date": iso_date,
            "meal_key": meal_key,
            "tenant_id": str(tenant_id),
        },
        current=current_summary,
        v2=v2_summary,
        matches=matches,
        mismatches=mismatches,
        caveats=caveats,
    )


def build_day_comparison_report(comparison: PlaneraComparison) -> str:
    lines: list[str] = []

    lines.append("Planera 1.0 vs Planera 2.0 Day Comparison")
    lines.append(f"  site_id: {comparison.context.get('site_id', '')}")
    lines.append(f"  date: {comparison.context.get('date', '')}")
    lines.append(f"  meal_key: {comparison.context.get('meal_key', '')}")

    lines.append("")
    lines.append("Current Planera 1.0 Summary")
    lines.append(f"  unit_count: {len(comparison.current.unit_ids)}")
    lines.append(f"  baseline_total: {comparison.current.totals['baseline_total']}")
    lines.append(f"  deviation_total: {comparison.current.totals['deviation_total']}")
    lines.append(f"  normal_total: {comparison.current.totals['normal_total']}")

    lines.append("")
    lines.append("Planera 2.0 Summary")
    lines.append(f"  unit_count: {len(comparison.v2.unit_ids)}")
    lines.append(f"  baseline_total: {comparison.v2.totals['baseline_total']}")
    lines.append(f"  deviation_total: {comparison.v2.totals['deviation_total']}")
    lines.append(f"  normal_total: {comparison.v2.totals['normal_total']}")

    lines.append("")
    lines.append("Match / Mismatch")
    for key in sorted(comparison.matches.keys()):
        lines.append(f"  - {key}: {'match' if comparison.matches[key] else 'mismatch'}")
    if comparison.mismatches:
        lines.append("  Notes:")
        for note in comparison.mismatches:
            lines.append(f"    - {note}")

    lines.append("")
    lines.append("Caveats")
    for caveat in comparison.caveats:
        lines.append(f"  - {caveat}")

    return "\n".join(lines)
