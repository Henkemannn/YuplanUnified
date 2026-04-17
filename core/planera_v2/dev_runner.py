from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .adapters.kommun_from_weekview import build_plan_request_from_weekview_day
from .domain import PlanRequest, PlanResult
from .engine import compute_plan
from .formatter import (
    format_plan_result,
    format_plan_result_clean,
    format_plan_result_kitchen_view,
)


@dataclass(frozen=True)
class PlaneraV2DevRun:
    request: PlanRequest
    result: PlanResult
    formatted_debug: str
    formatted_clean: str
    formatted_kitchen: str


def run_planera_v2_from_current_day(
    tenant_id: int | str,
    site_id: str,
    iso_date: str,
    meal_key: str,
    *,
    planera_service: object | None = None,
    departments: Iterable[tuple[str, str]] | None = None,
    component_id: str | None = None,
    component_name: str | None = None,
    component_role: str | None = None,
    component_mode: str | None = None,
) -> PlaneraV2DevRun:
    request = build_plan_request_from_weekview_day(
        tenant_id=tenant_id,
        site_id=site_id,
        iso_date=iso_date,
        meal=meal_key,
        planera_service=planera_service,
        departments=departments,
        component_id=component_id,
        component_name=component_name,
        component_role=component_role,
        component_mode=component_mode,
    )
    result = compute_plan(request)

    return PlaneraV2DevRun(
        request=request,
        result=result,
        formatted_debug=format_plan_result(result),
        formatted_clean=format_plan_result_clean(result),
        formatted_kitchen=format_plan_result_kitchen_view(result),
    )


def format_dev_run_report(run: PlaneraV2DevRun) -> str:
    lines: list[str] = []

    context = run.request.context or {}
    lines.append("Planera 2.0 Dev Run")
    lines.append(f"  site_id: {context.get('site_id', '')}")
    lines.append(f"  date: {context.get('date', '')}")
    lines.append(f"  meal_key: {context.get('meal_key', '')}")
    if context.get("component_id"):
        lines.append(f"  component_id: {context.get('component_id', '')}")
    if context.get("component_name"):
        lines.append(f"  component_name: {context.get('component_name', '')}")
    if context.get("component_role"):
        lines.append(f"  component_role: {context.get('component_role', '')}")
    if context.get("component_mode"):
        lines.append(f"  component_mode: {context.get('component_mode', '')}")
    lines.append(f"  baseline: {run.request.baseline}")

    lines.append("")
    lines.append("Units:")
    if run.request.units:
        for unit in run.request.units:
            lines.append(f"  - {unit.unit_id}: baseline_total={unit.baseline_total}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Deviations:")
    if run.request.deviations:
        for deviation in run.request.deviations:
            lines.append(
                "  - "
                f"unit_id={deviation.unit_id or ''}, "
                f"form={deviation.form}, "
                f"categories={','.join(deviation.category_keys)}, "
                f"quantity={deviation.quantity}"
            )
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("=== Debug Formatter ===")
    lines.append(run.formatted_debug)

    lines.append("")
    lines.append("=== Clean Formatter ===")
    lines.append(run.formatted_clean)

    lines.append("")
    lines.append("=== Kitchen Formatter ===")
    lines.append(run.formatted_kitchen)

    return "\n".join(lines)
