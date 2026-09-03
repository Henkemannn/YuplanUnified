from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .acceptance import ProductionAcceptanceResult, validate_plan_request_for_production
from .adapters.kommun_from_requirement_groups import build_planning_slice_from_requirement_groups
from .domain import PlanRequest, PlanResult
from .engine import compute_plan

ProductionAcceptanceVerdict = Literal["PASS", "BLOCKED"]


@dataclass(frozen=True, slots=True)
class ProductionShadowRun:
    request: PlanRequest
    acceptance: ProductionAcceptanceResult
    diagnostic_result: PlanResult | None

    @property
    def production_acceptance_verdict(self) -> ProductionAcceptanceVerdict:
        return "PASS" if self.acceptance.accepted else "BLOCKED"

    @property
    def is_production_accepted(self) -> bool:
        return self.acceptance.accepted


def run_plan_request_in_production_shadow(
    request: PlanRequest,
    *,
    expected_unit_ids: Iterable[str] | None = None,
    compute_diagnostics_when_blocked: bool = True,
) -> ProductionShadowRun:
    acceptance = validate_plan_request_for_production(request, expected_unit_ids=expected_unit_ids)

    if acceptance.accepted:
        return ProductionShadowRun(
            request=request,
            acceptance=acceptance,
            diagnostic_result=compute_plan(request),
        )

    diagnostic_result = compute_plan(request) if compute_diagnostics_when_blocked else None
    return ProductionShadowRun(
        request=request,
        acceptance=acceptance,
        diagnostic_result=diagnostic_result,
    )


def run_canonical_requirement_groups_in_production_shadow(
    *,
    site_id: str,
    service_date,
    meal_key: str,
    unit_baselines: dict[str, object],
    expected_unit_ids: Iterable[str] | None,
    context: dict[str, object] | None = None,
    compute_diagnostics_when_blocked: bool = True,
) -> ProductionShadowRun:
    planning_slice = build_planning_slice_from_requirement_groups(
        site_id=site_id,
        service_date=service_date,
        meal_key=meal_key,
        unit_baselines=unit_baselines,
        context=context,
    )
    request = planning_slice.to_plan_request()
    return run_plan_request_in_production_shadow(
        request,
        expected_unit_ids=expected_unit_ids,
        compute_diagnostics_when_blocked=compute_diagnostics_when_blocked,
    )


__all__ = [
    "ProductionAcceptanceVerdict",
    "ProductionShadowRun",
    "run_canonical_requirement_groups_in_production_shadow",
    "run_plan_request_in_production_shadow",
]
