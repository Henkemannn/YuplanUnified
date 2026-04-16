from __future__ import annotations

from .domain import PlanResult


def _parse_combination_key(key: str) -> tuple[str, str]:
    parts = key.split("__")
    form = parts[0] if parts else key
    categories = "__".join(parts[1:]) if len(parts) > 1 else ""
    return form, categories


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


def format_plan_result_clean(result: PlanResult) -> str:
    """Format a production-oriented summary, hiding zero-value rows."""
    lines: list[str] = []

    lines.append("Plan Result")
    lines.append("Totals:")
    lines.append(f"  Baseline: {result.totals.baseline_total}")
    lines.append(f"  Deviations: {result.totals.deviation_total}")
    lines.append(f"  Normal: {result.totals.normal_total}")

    lines.append("Production by form:")
    non_zero_forms = [(k, v) for k, v in result.per_form.items() if v != 0]
    if non_zero_forms:
        for key, value in non_zero_forms:
            lines.append(f"  - {key}: {value}")
    else:
        lines.append("  (none)")

    lines.append("Production by combination:")
    non_zero_combinations = [(k, v) for k, v in result.per_combination.items() if v != 0]
    if non_zero_combinations:
        for key, value in non_zero_combinations:
            lines.append(f"  - {key}: {value}")
    else:
        lines.append("  (none)")

    lines.append("Production by unit:")
    non_zero_units = [(k, v) for k, v in result.per_unit.items() if v != 0]
    if non_zero_units:
        for key, value in non_zero_units:
            lines.append(f"  - {key}: {value}")
    else:
        lines.append("  (none)")

    if result.warnings:
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines)


def format_plan_result_kitchen_view(result: PlanResult) -> str:
    lines: list[str] = []

    shown_units: list[str] = []
    for unit_id in sorted(result.per_unit_breakdown.keys()):
        breakdown = result.per_unit_breakdown[unit_id]
        has_non_zero_special = any(value != 0 for value in breakdown.per_combination.values())
        has_non_zero_known_normal = breakdown.normal_total != 0
        if has_non_zero_special or has_non_zero_known_normal:
            shown_units.append(unit_id)

    for unit_id in shown_units:
        breakdown = result.per_unit_breakdown[unit_id]
        special_total = breakdown.deviation_total

        has_known_normal = not (breakdown.baseline_total == 0 and breakdown.normal_total == 0)
        if has_known_normal:
            normal_display = str(breakdown.normal_total)
            unit_total_display = str(breakdown.normal_total + special_total)
        else:
            normal_display = "not available yet"
            unit_total_display = "not available yet"

        grouped_by_form: dict[str, dict[str, int]] = {}
        for combo_key, qty in breakdown.per_combination.items():
            if qty == 0:
                continue
            form, categories = _parse_combination_key(combo_key)
            if not categories:
                continue
            form_bucket = grouped_by_form.setdefault(form, {})
            form_bucket[categories] = form_bucket.get(categories, 0) + qty

        lines.append(f"Unit: {unit_id}")
        lines.append("  Normalkost:")
        lines.append(f"    total: {normal_display}")
        lines.append("")

        lines.append("  Specialkost:")
        shown_forms = [form for form, cats in grouped_by_form.items() if any(v != 0 for v in cats.values())]
        if shown_forms:
            for form in sorted(shown_forms):
                lines.append(f"    {form}:")
                categories = grouped_by_form[form]
                for category_key in sorted(categories.keys()):
                    value = categories[category_key]
                    if value == 0:
                        continue
                    lines.append(f"      {category_key}: {value}")
        else:
            lines.append("    (none)")

        lines.append("")
        lines.append(f"  Total: {unit_total_display}")
        lines.append("")

    lines.append("TOTAL")
    lines.append(f"  Normalkost: {result.totals.normal_total}")
    lines.append(f"  Specialkost: {result.totals.deviation_total}")
    lines.append(f"  Total: {result.totals.baseline_total}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines)
