from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping, Sequence
from .planera_service import PlaneraService
from .planera_v2.day_context_resolver import resolve_kommun_day_business_context
from .planera_v2.day_orchestration import KommunDayBusinessContext, run_canonical_kommun_day

KommunDayApplicationMode = Literal["legacy", "shadow"]


@dataclass(frozen=True, slots=True)
class KommunDayMetricComparison:
    legacy: int
    canonical: int
    matched: bool


@dataclass(frozen=True, slots=True)
class KommunDayMealComparison:
    legacy_department_ids: tuple[str, ...]
    canonical_department_ids: tuple[str, ...]
    missing_legacy_department_ids: tuple[str, ...]
    missing_canonical_department_ids: tuple[str, ...]
    per_department: dict[str, dict[str, KommunDayMetricComparison]]
    totals: dict[str, KommunDayMetricComparison]
    matched: bool


@dataclass(frozen=True, slots=True)
class KommunDayApplicationComparison:
    meals: dict[str, KommunDayMealComparison]
    matched: bool


def build_legacy_kommun_day_payload(
    *,
    context: KommunDayBusinessContext,
    legacy_service: Any | None = None,
) -> dict[str, object]:
    service = legacy_service if legacy_service is not None else PlaneraService()
    departments = [
        (
            _normalize_id(getattr(department, "department_id", getattr(department, "id", ""))),
            _normalize_id(getattr(department, "department_name", getattr(department, "name", ""))),
        )
        for department in context.departments
        if _normalize_id(getattr(department, "department_id", getattr(department, "id", "")))
    ]
    payload = service.compute_day(context.tenant_id, context.site_id, context.service_date, departments)
    if not isinstance(payload, dict):
        raise TypeError("legacy PlaneraService.compute_day must return a dict payload")

    departments_value = payload.get("departments") if isinstance(payload.get("departments"), list) else []
    totals_value = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    return {
        "site_id": context.site_id,
        "site_name": context.site_name,
        "date": context.service_date,
        "meal_labels": {
            "lunch": _normalize_id(context.meal_labels.get("lunch")),
            "dinner": _normalize_id(context.meal_labels.get("dinner")),
        },
        "departments": departments_value,
        "totals": totals_value,
    }


def _normalize_id(value: object) -> str:
    return str(value or "").strip()


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summarize_meal_payload(payload: Mapping[str, object], meal_key: str) -> tuple[tuple[str, ...], dict[str, dict[str, int]], dict[str, int]]:
    departments = payload.get("departments")
    if not isinstance(departments, list):
        departments = []

    department_ids: list[str] = []
    per_department: dict[str, dict[str, int]] = {}

    for department in departments:
        if not isinstance(department, dict):
            continue
        department_id = _normalize_id(department.get("department_id"))
        if not department_id:
            continue
        department_ids.append(department_id)
        meals = department.get("meals") if isinstance(department.get("meals"), dict) else {}
        meal = meals.get(meal_key) if isinstance(meals.get(meal_key), dict) else {}
        residents_total = _to_int(meal.get("residents_total"), default=0)
        normal_diet_count = _to_int(meal.get("normal_diet_count"), default=0)
        special_diets = meal.get("special_diets") if isinstance(meal.get("special_diets"), list) else []
        deviation_total = 0
        for item in special_diets:
            if not isinstance(item, dict):
                continue
            deviation_total += max(0, _to_int(item.get("count"), default=0))
        per_department[department_id] = {
            "residents_total": residents_total,
            "deviation_total": deviation_total,
            "normal_diet_count": normal_diet_count,
        }

    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    meal_totals = totals.get(meal_key) if isinstance(totals.get(meal_key), dict) else {}
    summary_totals = {
        "residents_total": _to_int(meal_totals.get("residents_total"), default=0),
        "deviation_total": 0,
        "normal_diet_count": _to_int(meal_totals.get("normal_diet_count"), default=0),
    }
    special_diets = meal_totals.get("special_diets") if isinstance(meal_totals.get("special_diets"), list) else []
    for item in special_diets:
        if not isinstance(item, dict):
            continue
        summary_totals["deviation_total"] += max(0, _to_int(item.get("count"), default=0))

    return tuple(department_ids), per_department, summary_totals


def compare_kommun_day_payloads(
    legacy_payload: Mapping[str, object],
    canonical_payload: Mapping[str, object],
) -> KommunDayApplicationComparison:
    meals: dict[str, KommunDayMealComparison] = {}
    overall_matched = True

    for meal_key in ("lunch", "dinner"):
        legacy_department_ids, legacy_department_metrics, legacy_totals = _summarize_meal_payload(legacy_payload, meal_key)
        canonical_department_ids, canonical_department_metrics, canonical_totals = _summarize_meal_payload(canonical_payload, meal_key)

        legacy_department_set = tuple(sorted(set(legacy_department_ids)))
        canonical_department_set = tuple(sorted(set(canonical_department_ids)))
        missing_legacy_department_ids = tuple(sorted(set(canonical_department_set) - set(legacy_department_set)))
        missing_canonical_department_ids = tuple(sorted(set(legacy_department_set) - set(canonical_department_set)))
        common_department_ids = tuple(sorted(set(legacy_department_metrics) & set(canonical_department_metrics)))

        per_department: dict[str, dict[str, KommunDayMetricComparison]] = {}
        meal_matched = not missing_legacy_department_ids and not missing_canonical_department_ids

        for department_id in common_department_ids:
            legacy_metrics = legacy_department_metrics[department_id]
            canonical_metrics = canonical_department_metrics[department_id]
            per_department[department_id] = {
                metric_name: KommunDayMetricComparison(
                    legacy=legacy_metrics[metric_name],
                    canonical=canonical_metrics[metric_name],
                    matched=legacy_metrics[metric_name] == canonical_metrics[metric_name],
                )
                for metric_name in ("residents_total", "deviation_total", "normal_diet_count")
            }
            meal_matched = meal_matched and all(metric.matched for metric in per_department[department_id].values())

        totals = {
            metric_name: KommunDayMetricComparison(
                legacy=legacy_totals[metric_name],
                canonical=canonical_totals[metric_name],
                matched=legacy_totals[metric_name] == canonical_totals[metric_name],
            )
            for metric_name in ("residents_total", "deviation_total", "normal_diet_count")
        }
        meal_matched = meal_matched and all(metric.matched for metric in totals.values())

        meals[meal_key] = KommunDayMealComparison(
            legacy_department_ids=legacy_department_set,
            canonical_department_ids=canonical_department_set,
            missing_legacy_department_ids=missing_legacy_department_ids,
            missing_canonical_department_ids=missing_canonical_department_ids,
            per_department=per_department,
            totals=totals,
            matched=meal_matched,
        )
        overall_matched = overall_matched and meal_matched

    return KommunDayApplicationComparison(meals=meals, matched=overall_matched)


def _comparison_log_payload(comparison: KommunDayApplicationComparison) -> dict[str, object]:
    return asdict(comparison)


def _default_logger() -> logging.Logger:
    return logging.getLogger(__name__)


def _run_shadow_comparison(
    *,
    context,
    legacy_payload: Mapping[str, object],
    logger: Any,
) -> None:
    try:
        canonical_payload = run_canonical_kommun_day(context)
    except Exception as exc:
        logger.exception(
            "planera_day_canonical_shadow_failed",
            extra={
                "tenant_id": str(context.tenant_id),
                "site_id": context.site_id,
                "service_date": context.service_date,
                "error": str(exc),
            },
        )
        return

    if not isinstance(canonical_payload, dict):
        logger.warning(
            "planera_day_canonical_shadow_invalid_payload",
            extra={
                "tenant_id": str(context.tenant_id),
                "site_id": context.site_id,
                "service_date": context.service_date,
            },
        )
        return

    comparison = compare_kommun_day_payloads(legacy_payload, canonical_payload)
    log_payload = {
        "tenant_id": str(context.tenant_id),
        "site_id": context.site_id,
        "service_date": context.service_date,
        "comparison": _comparison_log_payload(comparison),
    }
    if comparison.matched:
        logger.info("planera_day_shadow_match", extra=log_payload)
    else:
        logger.warning("planera_day_shadow_mismatch", extra=log_payload)


def run_kommun_day_application(
    *,
    mode: KommunDayApplicationMode,
    tenant_id: int | str,
    site_id: str,
    service_date,
    meal_labels: Mapping[str, str],
    department_id: str | None = None,
    legacy_service: Any | None = None,
    logger: Any | None = None,
) -> dict[str, object]:
    if mode not in ("legacy", "shadow"):
        raise ValueError("unsupported application mode")

    context = resolve_kommun_day_business_context(
        tenant_id=tenant_id,
        site_id=site_id,
        service_date=service_date,
        meal_labels=meal_labels,
        department_id=department_id,
    )
    legacy_payload = build_legacy_kommun_day_payload(
        context=context,
        legacy_service=legacy_service,
    )

    if mode == "shadow":
        _run_shadow_comparison(
            context=context,
            legacy_payload=legacy_payload,
            logger=logger or _default_logger(),
        )

    return legacy_payload


__all__ = [
    "KommunDayApplicationComparison",
    "KommunDayApplicationMode",
    "KommunDayMealComparison",
    "KommunDayMetricComparison",
    "build_legacy_kommun_day_payload",
    "compare_kommun_day_payloads",
    "run_kommun_day_application",
]