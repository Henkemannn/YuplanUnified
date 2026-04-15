from __future__ import annotations

from .domain import PlanResult


def format_plan_result(result: PlanResult) -> str:
    lines: list[str] = []

    lines.append("Totals:")
    lines.append(f"  baseline_total: {result.totals.baseline_total}")
    lines.append(f"  deviation_total: {result.totals.deviation_total}")
    lines.append(f"  normal_total: {result.totals.normal_total}")

    lines.append("Per form:")
    for key, value in result.per_form.items():
        lines.append(f"  {key}: {value}")

    lines.append("Per combination:")
    for key, value in result.per_combination.items():
        lines.append(f"  {key}: {value}")

    lines.append("Per unit:")
    for key, value in result.per_unit.items():
        lines.append(f"  {key}: {value}")

    lines.append("Warnings:")
    if result.warnings:
        for warning in result.warnings:
            lines.append(f"  - {warning}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)
