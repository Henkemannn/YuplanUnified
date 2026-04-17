from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .models import Deviation, PlanRequest, PlanResult

_KEY_SANITIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize_key(value: str | None) -> str:
    """Normalize a key to deterministic snake_case lowercase."""
    raw = str(value or "").strip().lower()
    normalized = _KEY_SANITIZE_RE.sub("_", raw).strip("_")
    return normalized


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_categories(item: Mapping[str, Any] | Deviation) -> tuple[list[str], bool]:
    if isinstance(item, Deviation):
        raw_list = list(item.category_keys)
        if item.category_key is not None:
            raw_list.append(item.category_key)
    else:
        raw_keys = item.get("category_keys")
        raw_list = []
        if isinstance(raw_keys, list):
            raw_list.extend(str(v) for v in raw_keys)
        elif isinstance(raw_keys, tuple):
            raw_list.extend(str(v) for v in raw_keys)
        raw_single = item.get("category_key")
        if raw_single is not None:
            raw_list.append(str(raw_single))

    out: list[str] = []
    invalid_seen = False
    for raw in raw_list:
        key = normalize_key(raw)
        if not key:
            invalid_seen = True
            continue
        out.append(key)

    if not out:
        return ["unknown_category"], True

    # Deduplicate and sort categories for deterministic multi-category keys.
    return sorted(set(out)), invalid_seen


def _iter_deviations(request: PlanRequest | Mapping[str, Any]) -> Iterable[Mapping[str, Any] | Deviation]:
    if isinstance(request, PlanRequest):
        return request.deviations
    raw = request.get("deviations")
    if not isinstance(raw, list) and not isinstance(raw, tuple):
        return ()
    return raw


def _get_baseline(request: PlanRequest | Mapping[str, Any]) -> int:
    if isinstance(request, PlanRequest):
        baseline = _as_int(request.baseline)
    else:
        baseline = _as_int(request.get("baseline"))
    return baseline


def _get_known_categories(request: PlanRequest | Mapping[str, Any]) -> set[str]:
    if isinstance(request, PlanRequest):
        context = request.context
    else:
        context = request.get("context") if isinstance(request.get("context"), dict) else {}
    raw = context.get("known_category_keys") if isinstance(context, dict) else None
    if not isinstance(raw, list) and not isinstance(raw, tuple):
        return set()
    out = {normalize_key(str(v)) for v in raw}
    return {v for v in out if v}


def _warn_once(warnings: list[str], seen: set[str], message: str) -> None:
    if message in seen:
        return
    seen.add(message)
    warnings.append(message)


def compute_plan(request: PlanRequest | Mapping[str, Any]) -> PlanResult:
    """Compute a Planera 2.0 deterministic plan result.

    The function is pure and side-effect free: it only transforms input to output.
    """
    # STEP 1: Init result structure.
    totals = {"baseline_total": 0, "deviation_total": 0, "normal_total": 0}
    per_form: dict[str, int] = {}
    per_combination: dict[str, int] = {}
    per_unit: dict[str, int] = {}
    warnings: list[str] = []
    warnings_seen: set[str] = set()

    # STEP 2: Validate baseline.
    baseline = _get_baseline(request)
    if baseline < 0:
        _warn_once(warnings, warnings_seen, "Invalid baseline (<0). Baseline clamped to 0.")
        baseline = 0
    totals["baseline_total"] = baseline

    known_categories = _get_known_categories(request)

    # STEP 3-6: Normalize keys, build combinations, and sum totals.
    for index, raw_dev in enumerate(_iter_deviations(request)):
        if isinstance(raw_dev, Deviation):
            form_raw = raw_dev.form
            quantity = _as_int(raw_dev.quantity)
            unit_id = raw_dev.unit_id
        elif isinstance(raw_dev, Mapping):
            form_raw = str(raw_dev.get("form") or "")
            quantity = _as_int(raw_dev.get("quantity"))
            unit_id = raw_dev.get("unit_id")
        else:
            _warn_once(warnings, warnings_seen, f"Deviation {index} ignored: invalid item type.")
            continue

        form = normalize_key(form_raw)
        if not form:
            _warn_once(warnings, warnings_seen, f"Deviation {index} ignored: missing form.")
            continue

        if quantity < 0:
            _warn_once(
                warnings,
                warnings_seen,
                f"Deviation {index} has negative quantity. Quantity clamped to 0.",
            )
            quantity = 0

        categories, invalid_category = _normalize_categories(raw_dev)
        if invalid_category:
            _warn_once(
                warnings,
                warnings_seen,
                f"Deviation {index} has invalid or missing category. Using unknown_category.",
            )

        for category in categories:
            if category == "unknown_category":
                continue
            if known_categories and category not in known_categories:
                _warn_once(warnings, warnings_seen, f"Unknown category: {category}")

        combination_key = "__".join([form, *categories])

        per_form[form] = per_form.get(form, 0) + quantity
        per_combination[combination_key] = per_combination.get(combination_key, 0) + quantity
        totals["deviation_total"] += quantity

        if unit_id is not None and str(unit_id).strip():
            unit_key = str(unit_id).strip()
            per_unit[unit_key] = per_unit.get(unit_key, 0) + quantity

    # STEP 7-8: Compute normal and finalize totals.
    normal_total = totals["baseline_total"] - totals["deviation_total"]
    if normal_total < 0:
        normal_total = 0
        _warn_once(warnings, warnings_seen, "Deviation exceeds baseline. normal_total clamped to 0.")
    totals["normal_total"] = normal_total

    # STEP 9: Sort output for deterministic ordering.
    totals_sorted = dict(sorted(totals.items()))
    per_form_sorted = dict(sorted(per_form.items()))
    per_combination_sorted = dict(sorted(per_combination.items()))
    per_unit_sorted = dict(sorted(per_unit.items()))

    # STEP 10: Return result.
    return PlanResult(
        totals=totals_sorted,
        per_form=per_form_sorted,
        per_combination=per_combination_sorted,
        per_unit=per_unit_sorted,
        warnings=warnings,
    )
