from __future__ import annotations

from typing import Any

from .domain import Deviation, PlanRequest, PlanResult
from .engine import compute_plan


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_plan_request_from_adapter_payload(payload: dict[str, Any]) -> PlanRequest:
    baseline = _to_int(payload.get("baseline"), default=0)

    raw_context = payload.get("context")
    context = dict(raw_context) if isinstance(raw_context, dict) else {}

    deviations: list[Deviation] = []
    raw_deviations = payload.get("deviations")
    if isinstance(raw_deviations, list):
        for raw in raw_deviations:
            if not isinstance(raw, dict):
                continue

            form = str(raw.get("form") or "")

            raw_categories = raw.get("category_keys")
            category_keys: list[str] = []
            if isinstance(raw_categories, list):
                category_keys = [str(item) for item in raw_categories]

            quantity = _to_int(raw.get("quantity"), default=0)

            unit_raw = raw.get("unit_id")
            unit_id = str(unit_raw) if unit_raw is not None else None

            deviations.append(
                Deviation(
                    form=form,
                    category_keys=category_keys,
                    quantity=quantity,
                    unit_id=unit_id,
                )
            )

    return PlanRequest(baseline=baseline, deviations=deviations, context=context)


def run_plan(request: PlanRequest) -> PlanResult:
    return compute_plan(request)


def run_plan_from_payload(payload: dict[str, Any]) -> PlanResult:
    request = build_plan_request_from_adapter_payload(payload)
    return run_plan(request)
