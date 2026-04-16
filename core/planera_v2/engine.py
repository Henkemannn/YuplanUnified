from __future__ import annotations

from .domain import PlanRequest, PlanResult, Totals, UnitBreakdown
from .utils import build_combination_key, normalize_key


def compute_plan(request: PlanRequest) -> PlanResult:
    per_form: dict[str, int] = {}
    per_combination: dict[str, int] = {}
    per_unit: dict[str, int] = {}
    per_unit_breakdown_acc: dict[str, dict[str, object]] = {}
    warnings: list[str] = []

    unit_baselines: dict[str, int] = {}
    for unit in request.units:
        unit_key = str(unit.unit_id).strip()
        if not unit_key:
            continue
        unit_baseline = int(unit.baseline_total)
        if unit_baseline < 0:
            warnings.append(f"unit[{unit_key}] baseline < 0 clamped to 0")
            unit_baseline = 0
        unit_baselines[unit_key] = unit_baseline
        per_unit_breakdown_acc[unit_key] = {
            "has_baseline": True,
            "baseline_total": unit_baseline,
            "deviation_total": 0,
            "per_combination": {},
            "per_form": {},
        }

    baseline = int(request.baseline)
    if baseline < 0:
        warnings.append("baseline < 0 clamped to 0")
        baseline = 0

    deviation_total = 0

    for index, deviation in enumerate(request.deviations):
        form_key = normalize_key(deviation.form)
        if not form_key:
            warnings.append(f"deviation[{index}] missing form")
            continue

        quantity = int(deviation.quantity)
        if quantity < 0:
            warnings.append(f"deviation[{index}] quantity < 0 clamped to 0")
            quantity = 0

        normalized_categories: list[str] = []
        for category in deviation.category_keys:
            normalized = normalize_key(category)
            if normalized:
                normalized_categories.append(normalized)

        # Deviations without category_keys are skipped and only produce a warning.
        if not normalized_categories:
            warnings.append(f"deviation[{index}] missing category_key")
            continue

        normalized_categories = sorted(set(normalized_categories))

        combination_key = build_combination_key(form_key, normalized_categories)

        per_form[form_key] = per_form.get(form_key, 0) + quantity
        per_combination[combination_key] = per_combination.get(combination_key, 0) + quantity
        deviation_total += quantity

        if deviation.unit_id is not None and str(deviation.unit_id).strip():
            unit_key = str(deviation.unit_id).strip()
            per_unit[unit_key] = per_unit.get(unit_key, 0) + quantity

            unit_bucket = per_unit_breakdown_acc.setdefault(
                unit_key,
                {
                    "has_baseline": unit_key in unit_baselines,
                    "baseline_total": unit_baselines.get(unit_key, 0),
                    "deviation_total": 0,
                    "per_combination": {},
                    "per_form": {},
                },
            )
            unit_bucket["deviation_total"] = int(unit_bucket["deviation_total"]) + quantity

            unit_per_combination = unit_bucket["per_combination"]
            if isinstance(unit_per_combination, dict):
                unit_per_combination[combination_key] = int(unit_per_combination.get(combination_key, 0)) + quantity

            unit_per_form = unit_bucket["per_form"]
            if isinstance(unit_per_form, dict):
                unit_per_form[form_key] = int(unit_per_form.get(form_key, 0)) + quantity

    normal_total = baseline - deviation_total
    if normal_total < 0:
        warnings.append("deviation exceeds baseline; normal_total clamped to 0")
        normal_total = 0

    per_unit_breakdown: dict[str, UnitBreakdown] = {}
    for unit_key in sorted(per_unit_breakdown_acc.keys()):
        bucket = per_unit_breakdown_acc[unit_key]
        unit_per_combination = bucket.get("per_combination")
        if not isinstance(unit_per_combination, dict):
            unit_per_combination = {}
        unit_per_form = bucket.get("per_form")
        if not isinstance(unit_per_form, dict):
            unit_per_form = {}

        has_baseline = bool(bucket.get("has_baseline", False))
        baseline_total = int(bucket.get("baseline_total", 0)) if has_baseline else 0
        deviation_total_for_unit = int(bucket.get("deviation_total", 0))

        if has_baseline:
            normal_total_for_unit = baseline_total - deviation_total_for_unit
            if normal_total_for_unit < 0:
                warnings.append(f"unit[{unit_key}] deviation exceeds baseline; normal_total clamped to 0")
                normal_total_for_unit = 0
        else:
            # No authoritative unit baseline in request.units -> keep conservative values.
            normal_total_for_unit = 0

        per_unit_breakdown[unit_key] = UnitBreakdown(
            baseline_total=baseline_total,
            deviation_total=deviation_total_for_unit,
            normal_total=normal_total_for_unit,
            per_combination=dict(sorted((str(k), int(v)) for k, v in unit_per_combination.items())),
            per_form=dict(sorted((str(k), int(v)) for k, v in unit_per_form.items())),
        )

    return PlanResult(
        totals=Totals(
            baseline_total=baseline,
            deviation_total=deviation_total,
            normal_total=normal_total,
        ),
        per_form=dict(sorted(per_form.items())),
        per_combination=dict(sorted(per_combination.items())),
        per_unit=dict(sorted(per_unit.items())),
        per_unit_breakdown=per_unit_breakdown,
        warnings=warnings,
    )
