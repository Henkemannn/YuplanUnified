from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from sqlalchemy import text

from ..db import get_session
from ..planera_service import PlaneraService
from .acceptance import ProductionAcceptanceResult
from .shadow import ProductionShadowRun, run_canonical_requirement_groups_in_production_shadow
from .utils import normalize_key
from .dev_runner import PlaneraV2DevRun, run_planera_v2_from_current_day, run_planera_v2_from_day_payload


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
    parity_verdict: str
    compatibility_verdict: str
    compatibility_notes: list[str]


@dataclass(frozen=True)
class CanonicalPlaneraSummary:
    unit_ids: list[str]
    unit_baselines: dict[str, int]
    unit_deviation_totals: dict[str, int]
    unit_normal_totals: dict[str, int]
    totals: dict[str, int]


@dataclass(frozen=True)
class CanonicalPlaneraComparison:
    context: dict[str, object]
    current: CanonicalPlaneraSummary
    canonical_v2: CanonicalPlaneraSummary
    production_acceptance: ProductionAcceptanceResult
    matches: dict[str, bool]
    notes: list[str]
    baseline_parity_verdict: str
    numerical_parity_verdict: str
    representation_verdict: str
    compatibility_verdict: str

    @property
    def production_acceptance_verdict(self) -> str:
        return "PASS" if self.production_acceptance.accepted else "BLOCKED"

    @property
    def production_acceptance_issue_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.production_acceptance.issues)


@dataclass(frozen=True)
class ThreeWayPlaneraComparison:
    legacy: PlaneraComparison
    canonical: CanonicalPlaneraComparison


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_meal_key(value: object) -> str:
    return str(value or "").strip().lower()


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
            bucket_key = category_key
            category_map[bucket_key] = category_map.get(bucket_key, 0) + quantity

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

    unit_special_deviations: dict[str, dict[str, int]] = {unit.unit_id: {} for unit in run.request.units}
    for deviation in run.request.deviations:
        unit_id = str(deviation.unit_id or "").strip()
        if not unit_id:
            continue
        if not deviation.category_keys:
            continue
        normalized_categories = sorted({normalize_key(category) for category in deviation.category_keys if normalize_key(category)})
        if not normalized_categories:
            continue
        category_key = "__".join(normalized_categories)
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


def _extract_unit_baselines_from_day_payload(day_payload: dict[str, Any], meal_key: str) -> dict[str, int]:
    unit_baselines: dict[str, int] = {}
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
    return dict(sorted(unit_baselines.items()))


def _summarize_current_day_numeric(day_payload: dict[str, Any], meal_key: str) -> CanonicalPlaneraSummary:
    unit_baselines: dict[str, int] = {}
    unit_deviation_totals: dict[str, int] = {}
    unit_normal_totals: dict[str, int] = {}
    departments = day_payload.get("departments") if isinstance(day_payload.get("departments"), list) else []

    for dep in departments:
        if not isinstance(dep, dict):
            continue
        unit_id = str(dep.get("department_id") or "").strip()
        if not unit_id:
            continue

        meals = dep.get("meals") if isinstance(dep.get("meals"), dict) else {}
        meal_data = meals.get(meal_key) if isinstance(meals.get(meal_key), dict) else {}

        baseline_total = _to_int(meal_data.get("residents_total"), default=0)
        if baseline_total < 0:
            baseline_total = 0

        deviation_total = 0
        special_diets = meal_data.get("special_diets") if isinstance(meal_data.get("special_diets"), list) else []
        for item in special_diets:
            if not isinstance(item, dict):
                continue
            quantity = _to_int(item.get("count"), default=0)
            if quantity > 0:
                deviation_total += quantity

        normal_total = baseline_total - deviation_total
        if normal_total < 0:
            normal_total = 0

        unit_baselines[unit_id] = baseline_total
        unit_deviation_totals[unit_id] = deviation_total
        unit_normal_totals[unit_id] = normal_total

    total_baseline = sum(unit_baselines.values())
    total_deviation = sum(unit_deviation_totals.values())
    total_normal = sum(unit_normal_totals.values())

    return CanonicalPlaneraSummary(
        unit_ids=sorted(unit_baselines.keys()),
        unit_baselines=dict(sorted(unit_baselines.items())),
        unit_deviation_totals=dict(sorted(unit_deviation_totals.items())),
        unit_normal_totals=dict(sorted(unit_normal_totals.items())),
        totals={
            "baseline_total": total_baseline,
            "deviation_total": total_deviation,
            "normal_total": total_normal,
        },
    )


def _summarize_canonical_request_result(request: PlanRequest, result: PlanResult) -> CanonicalPlaneraSummary:
    unit_baselines: dict[str, int] = {}
    unit_deviation_totals: dict[str, int] = {}
    unit_normal_totals: dict[str, int] = {}

    for unit in request.units:
        unit_id = str(unit.unit_id).strip()
        if not unit_id:
            continue
        baseline_total = int(unit.baseline_total)
        breakdown = result.per_unit_breakdown.get(unit_id)
        deviation_total = int(breakdown.deviation_total) if breakdown is not None else 0
        normal_total = int(breakdown.normal_total) if breakdown is not None else max(0, baseline_total - deviation_total)
        unit_baselines[unit_id] = baseline_total
        unit_deviation_totals[unit_id] = deviation_total
        unit_normal_totals[unit_id] = normal_total

    return CanonicalPlaneraSummary(
        unit_ids=sorted(unit_baselines.keys()),
        unit_baselines=dict(sorted(unit_baselines.items())),
        unit_deviation_totals=dict(sorted(unit_deviation_totals.items())),
        unit_normal_totals=dict(sorted(unit_normal_totals.items())),
        totals={
            "baseline_total": int(result.totals.baseline_total),
            "deviation_total": int(result.totals.deviation_total),
            "normal_total": int(result.totals.normal_total),
        },
    )


def _summarize_canonical_run(run: PlaneraV2DevRun) -> CanonicalPlaneraSummary:
    return _summarize_canonical_request_result(run.request, run.result)


def _build_canonical_comparison_notes(
    current_summary: CanonicalPlaneraSummary,
    canonical_summary: CanonicalPlaneraSummary,
    compatibility_verdict: str,
    run: PlaneraV2DevRun,
) -> list[str]:
    notes: list[str] = []
    if current_summary.unit_ids != canonical_summary.unit_ids:
        notes.append("Unit list differs between current Planera and canonical Planera 2.0 run.")
    if current_summary.unit_baselines != canonical_summary.unit_baselines:
        notes.append("Unit baselines differ.")
    if current_summary.unit_deviation_totals != canonical_summary.unit_deviation_totals:
        notes.append("Per-unit deviation totals differ.")
    if current_summary.unit_normal_totals != canonical_summary.unit_normal_totals:
        notes.append("Per-unit normal totals differ.")
    if current_summary.totals["baseline_total"] != canonical_summary.totals["baseline_total"]:
        notes.append("Total baseline differs.")
    if current_summary.totals["deviation_total"] != canonical_summary.totals["deviation_total"]:
        notes.append("Total deviations differ.")
    if current_summary.totals["normal_total"] != canonical_summary.totals["normal_total"]:
        notes.append("Total normal differs.")
    if current_summary.totals["deviation_total"] or canonical_summary.totals["deviation_total"]:
        notes.append("Legacy bucket labels and canonical atomic requirement keys are not comparable by string identity.")
    return notes


def _canonical_compatibility_verdict(run: ProductionShadowRun) -> str:
    context = run.request.context or {}
    precision = str(context.get("compatibility_source_precision") or "").strip().lower()
    status = str(context.get("compatibility_status") or "").strip().lower()
    if precision == "canonical_atomic_groups" and status == "resolved":
        return "PASS"
    return "NOT_PROVABLE"


def _collect_canonical_notes(run: ProductionShadowRun) -> list[str]:
    notes: list[str] = []
    context = run.request.context or {}
    for source in (
        context.get("compatibility_warnings"),
        run.diagnostic_result.warnings if run.diagnostic_result is not None else [],
    ):
        if not isinstance(source, list):
            continue
        for item in source:
            note = str(item).strip()
            if note and note not in notes:
                notes.append(note)
    return notes


def _compare_canonical_summaries(
    current_summary: CanonicalPlaneraSummary,
    canonical_summary: CanonicalPlaneraSummary,
    run: ProductionShadowRun,
) -> CanonicalPlaneraComparison:
    matches = {
        "unit_list": current_summary.unit_ids == canonical_summary.unit_ids,
        "unit_baselines": current_summary.unit_baselines == canonical_summary.unit_baselines,
        "unit_deviation_totals": current_summary.unit_deviation_totals == canonical_summary.unit_deviation_totals,
        "unit_normal_totals": current_summary.unit_normal_totals == canonical_summary.unit_normal_totals,
        "total_baseline": current_summary.totals["baseline_total"] == canonical_summary.totals["baseline_total"],
        "total_deviations": current_summary.totals["deviation_total"] == canonical_summary.totals["deviation_total"],
        "total_normal": current_summary.totals["normal_total"] == canonical_summary.totals["normal_total"],
    }

    compatibility_verdict = _canonical_compatibility_verdict(run)
    baseline_parity_verdict = "PASS" if matches["unit_list"] and matches["unit_baselines"] and matches["total_baseline"] else "FAIL"
    numerical_parity_verdict = "PASS" if matches["unit_list"] and matches["unit_deviation_totals"] and matches["unit_normal_totals"] and matches["total_deviations"] and matches["total_normal"] else "FAIL"
    representation_verdict = (
        "PASS"
        if current_summary.totals["deviation_total"] == 0 and canonical_summary.totals["deviation_total"] == 0
        else "NOT_COMPARABLE"
    )
    notes = _build_canonical_comparison_notes(current_summary, canonical_summary, compatibility_verdict, run)
    notes.extend(_collect_canonical_notes(run))

    return CanonicalPlaneraComparison(
        context={
            "site_id": str((run.request.context or {}).get("site_id") or ""),
            "date": str((run.request.context or {}).get("date") or ""),
            "meal_key": str((run.request.context or {}).get("meal_key") or ""),
            "tenant_id": str((run.request.context or {}).get("tenant_id") or ""),
        },
        current=current_summary,
        canonical_v2=canonical_summary,
        production_acceptance=run.acceptance,
        matches=matches,
        notes=notes,
        baseline_parity_verdict=baseline_parity_verdict,
        numerical_parity_verdict=numerical_parity_verdict,
        representation_verdict=representation_verdict,
        compatibility_verdict=compatibility_verdict,
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
        "Comparison is strongest on totals, unit baselines, and effective unit deviations.",
    ]

    compatibility_source_precision = str((run.request.context or {}).get("compatibility_source_precision") or "").strip().lower()
    compatibility_notes: list[str] = []
    raw_compatibility_warnings = (run.request.context or {}).get("compatibility_warnings")
    if isinstance(raw_compatibility_warnings, list):
        compatibility_notes.extend(str(item) for item in raw_compatibility_warnings if str(item).strip())
    if compatibility_source_precision == "legacy_aggregate":
        compatibility_verdict = "NOT_PROVABLE"
        if not compatibility_notes:
            compatibility_notes.append(
                "aggregate-only source data cannot prove recipient-level compatibility"
            )
    else:
        compatibility_verdict = "PASS"

    parity_verdict = "PASS" if not mismatches else "FAIL"

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
        parity_verdict=parity_verdict,
        compatibility_verdict=compatibility_verdict,
        compatibility_notes=compatibility_notes,
    )


def compare_current_planera_vs_v2_day_from_payload(
    day_payload: dict[str, Any],
    tenant_id: int | str,
    site_id: str,
    iso_date: str,
    meal_key: str,
    *,
    departments: Iterable[tuple[str, str]] | None = None,
    shadow_runner: Callable[..., PlaneraV2DevRun] = run_planera_v2_from_day_payload,
) -> PlaneraComparison:
    current_summary = _summarize_current_day(day_payload, meal_key)

    run = shadow_runner(
        day_payload,
        meal_key,
        site_id=site_id,
        iso_date=iso_date,
        tenant_id=tenant_id,
        departments=departments,
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
        "Comparison is strongest on totals, unit baselines, and effective unit deviations.",
    ]

    compatibility_source_precision = str((run.request.context or {}).get("compatibility_source_precision") or "").strip().lower()
    compatibility_notes: list[str] = []
    raw_compatibility_warnings = (run.request.context or {}).get("compatibility_warnings")
    if isinstance(raw_compatibility_warnings, list):
        compatibility_notes.extend(str(item) for item in raw_compatibility_warnings if str(item).strip())
    if compatibility_source_precision == "legacy_aggregate":
        compatibility_verdict = "NOT_PROVABLE"
        if not compatibility_notes:
            compatibility_notes.append(
                "aggregate-only source data cannot prove recipient-level compatibility"
            )
    else:
        compatibility_verdict = "PASS"

    parity_verdict = "PASS" if not mismatches else "FAIL"

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
        parity_verdict=parity_verdict,
        compatibility_verdict=compatibility_verdict,
        compatibility_notes=compatibility_notes,
    )


def compare_current_legacy_and_canonical_v2_day_from_payload(
    day_payload: dict[str, Any],
    tenant_id: int | str,
    site_id: str,
    iso_date: str,
    meal_key: str,
    *,
    departments: Iterable[tuple[str, str]] | None = None,
    expected_unit_ids: Iterable[str],
) -> ThreeWayPlaneraComparison:
    normalized_meal_key = _normalize_meal_key(meal_key)
    legacy = compare_current_planera_vs_v2_day_from_payload(
        day_payload,
        tenant_id=tenant_id,
        site_id=site_id,
        iso_date=iso_date,
        meal_key=normalized_meal_key,
        departments=departments,
    )

    current_summary = _summarize_current_day_numeric(day_payload, normalized_meal_key)
    extracted_unit_baselines = _extract_unit_baselines_from_day_payload(day_payload, normalized_meal_key)
    canonical_run = run_canonical_requirement_groups_in_production_shadow(
        site_id=site_id,
        service_date=iso_date,
        meal_key=normalized_meal_key,
        unit_baselines=extracted_unit_baselines,
        expected_unit_ids=expected_unit_ids,
        context={
            "source": "current_planera_day",
            "site_id": site_id,
            "date": iso_date,
            "meal_key": normalized_meal_key,
            "tenant_id": str(tenant_id),
            "compatibility_source_precision": "canonical_atomic_groups",
        },
        compute_diagnostics_when_blocked=True,
    )
    if canonical_run.diagnostic_result is None:
        raise RuntimeError("canonical diagnostic_result missing")
    canonical_comparison = _compare_canonical_summaries(
        current_summary,
        _summarize_canonical_request_result(canonical_run.request, canonical_run.diagnostic_result),
        canonical_run,
    )

    return ThreeWayPlaneraComparison(
        legacy=legacy,
        canonical=canonical_comparison,
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
    lines.append(f"  Parity verdict: {comparison.parity_verdict}")
    lines.append(f"  Compatibility verdict: {comparison.compatibility_verdict}")
    for key in sorted(comparison.matches.keys()):
        lines.append(f"  - {key}: {'match' if comparison.matches[key] else 'mismatch'}")
    if comparison.mismatches:
        lines.append("  Notes:")
        for note in comparison.mismatches:
            lines.append(f"    - {note}")

    if comparison.compatibility_notes:
        lines.append("")
        lines.append("Compatibility caveats")
        for note in comparison.compatibility_notes:
            lines.append(f"  - {note}")

    lines.append("")
    lines.append("Caveats")
    for caveat in comparison.caveats:
        lines.append(f"  - {caveat}")

    return "\n".join(lines)
