from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .domain import PlanRequest

AcceptanceSeverity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class ProductionAcceptanceIssue:
    code: str
    severity: AcceptanceSeverity
    message: str
    unit_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionAcceptanceResult:
    accepted: bool
    issues: tuple[ProductionAcceptanceIssue, ...] = ()


def _normalize_unit_id(value: object) -> str:
    return str(value or "").strip()


def _normalize_expected_unit_ids(expected_unit_ids: Iterable[str] | None) -> tuple[str, ...]:
    if expected_unit_ids is None:
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_unit_id in expected_unit_ids:
        unit_id = _normalize_unit_id(raw_unit_id)
        if not unit_id or unit_id in seen:
            continue
        seen.add(unit_id)
        normalized.append(unit_id)
    return tuple(sorted(normalized))


def _issue(
    code: str,
    severity: AcceptanceSeverity,
    message: str,
    *,
    unit_id: str | None = None,
) -> ProductionAcceptanceIssue:
    return ProductionAcceptanceIssue(code=code, severity=severity, message=message, unit_id=unit_id)


def validate_plan_request_for_production(
    request: PlanRequest,
    *,
    expected_unit_ids: Iterable[str] | None = None,
) -> ProductionAcceptanceResult:
    issues: list[ProductionAcceptanceIssue] = []

    unit_counts: dict[str, int] = {}
    unit_baselines: dict[str, int] = {}
    valid_unit_order: list[str] = []
    structural_unit_issues = False

    for unit in request.units:
        unit_id = _normalize_unit_id(unit.unit_id)
        baseline_total = int(unit.baseline_total)

        if not unit_id:
            issues.append(
                _issue(
                    "unit_id_empty",
                    "error",
                    "unit_id is blank",
                )
            )
            structural_unit_issues = True
            continue

        unit_counts[unit_id] = unit_counts.get(unit_id, 0) + 1
        if unit_counts[unit_id] == 1:
            valid_unit_order.append(unit_id)
            unit_baselines[unit_id] = baseline_total
        else:
            issues.append(
                _issue(
                    "duplicate_unit_id",
                    "error",
                    "unit_id appears more than once",
                    unit_id=unit_id,
                )
            )
            structural_unit_issues = True

        if baseline_total < 0:
            issues.append(
                _issue(
                    "unit_baseline_negative",
                    "error",
                    "unit baseline is negative",
                    unit_id=unit_id,
                )
            )
            structural_unit_issues = True

    baseline_total = int(request.baseline)
    global_baseline_valid = baseline_total >= 0
    if baseline_total < 0:
        issues.append(
            _issue(
                "global_baseline_negative",
                "error",
                "global baseline is negative",
            )
        )

    expected_unit_ids_normalized = _normalize_expected_unit_ids(expected_unit_ids)
    expected_unit_ids_exact_match = True
    if expected_unit_ids is not None:
        actual_unit_ids = tuple(sorted(unit_counts))
        missing_unit_ids = [unit_id for unit_id in expected_unit_ids_normalized if unit_id not in actual_unit_ids]
        unexpected_unit_ids = [unit_id for unit_id in actual_unit_ids if unit_id not in expected_unit_ids_normalized]
        expected_unit_ids_exact_match = not missing_unit_ids and not unexpected_unit_ids

        for unit_id in missing_unit_ids:
            issues.append(
                _issue(
                    "expected_unit_missing",
                    "error",
                    "expected unit is missing from the request",
                    unit_id=unit_id,
                )
            )

        for unit_id in unexpected_unit_ids:
            issues.append(
                _issue(
                    "unexpected_unit",
                    "error",
                    "request contains an unexpected unit",
                    unit_id=unit_id,
                )
            )

    if (
        expected_unit_ids is not None
        and global_baseline_valid
        and expected_unit_ids_exact_match
        and not structural_unit_issues
    ):
        authoritative_unit_baseline_total = sum(unit_baselines[unit_id] for unit_id in valid_unit_order)
        if baseline_total != authoritative_unit_baseline_total:
            issues.append(
                _issue(
                    "unit_baseline_sum_mismatch",
                    "error",
                    "request baseline does not match authoritative unit baseline sum",
                )
            )

    authoritative_unit_context = bool(valid_unit_order) or expected_unit_ids is not None
    per_unit_deviation_totals: dict[str, int] = {unit_id: 0 for unit_id in valid_unit_order}
    global_deviation_total = 0

    for deviation in request.deviations:
        quantity = int(deviation.quantity)
        unit_id = _normalize_unit_id(deviation.unit_id)
        deviation_blocked = False

        if quantity < 0:
            issues.append(
                _issue(
                    "deviation_quantity_negative",
                    "error",
                    "deviation quantity is negative",
                    unit_id=unit_id or None,
                )
            )
            deviation_blocked = True

        if unit_id:
            if unit_counts.get(unit_id, 0) != 1:
                issues.append(
                    _issue(
                        "deviation_unit_unknown",
                        "error",
                        "deviation references an unknown unit",
                        unit_id=unit_id,
                    )
                )
                deviation_blocked = True
        elif quantity > 0 and authoritative_unit_context:
            issues.append(
                _issue(
                    "deviation_unit_missing",
                    "error",
                    "deviation is missing a unit_id",
                )
            )
            deviation_blocked = True

        form = _normalize_unit_id(deviation.form)
        category_keys = [str(category_key).strip() for category_key in deviation.category_keys if str(category_key).strip()]

        if not form:
            issues.append(
                _issue(
                    "deviation_form_missing",
                    "error",
                    "deviation form is missing",
                    unit_id=unit_id or None,
                )
            )
            deviation_blocked = True

        if not category_keys:
            issues.append(
                _issue(
                    "deviation_category_missing",
                    "error",
                    "deviation category is missing",
                    unit_id=unit_id or None,
                )
            )
            deviation_blocked = True

        if deviation_blocked:
            continue

        if unit_id:
            per_unit_deviation_totals[unit_id] = per_unit_deviation_totals.get(unit_id, 0) + quantity

        global_deviation_total += quantity

    if baseline_total >= 0 and global_deviation_total > baseline_total:
        issues.append(
            _issue(
                "deviation_exceeds_baseline",
                "error",
                "global deviation total exceeds baseline",
            )
        )

    for unit_id in valid_unit_order:
        baseline_total_for_unit = int(unit_baselines[unit_id])
        if baseline_total_for_unit < 0:
            continue
        deviation_total_for_unit = int(per_unit_deviation_totals.get(unit_id, 0))
        if deviation_total_for_unit > baseline_total_for_unit:
            issues.append(
                _issue(
                    "unit_deviation_exceeds_baseline",
                    "error",
                    "unit deviation total exceeds baseline",
                    unit_id=unit_id,
                )
            )

    return ProductionAcceptanceResult(
        accepted=not any(issue.severity == "error" for issue in issues),
        issues=tuple(issues),
    )


__all__ = [
    "ProductionAcceptanceIssue",
    "ProductionAcceptanceResult",
    "validate_plan_request_for_production",
]
