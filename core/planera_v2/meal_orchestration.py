from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Literal

from ..planera_product2_page2_context import (
    Product2Page2DestinationVM,
    Product2Page2PlanningContext,
    Product2Page2PublicationIdentity,
    build_product2_page2_planning_context,
)
from ..planning_option_review import (
    REVIEW_STATE_NO_DEVIATIONS,
    REVIEW_STATE_UNREVIEWED,
    REVIEW_STATE_WITH_DEVIATIONS,
    PlanningOptionReviewError,
    PlanningOptionReviewService,
)
from .acceptance import ProductionAcceptanceIssue, ProductionAcceptanceResult, validate_plan_request_for_production
from .adapters.kommun_from_option_reviews import (
    KommunOptionReviewPlanningError,
    build_planning_slice_from_option_review,
)
from .domain import PlanResult, PlanningSlice
from .engine import compute_plan


MealBlockerCode = Literal[
    "UNASSIGNED_DESTINATIONS",
    "UNREVIEWED_OPTIONS",
    "STALE_REVIEWS",
    "INVALID_OPTION_PLAN",
]

_BLOCKER_ORDER: tuple[MealBlockerCode, ...] = (
    "UNASSIGNED_DESTINATIONS",
    "UNREVIEWED_OPTIONS",
    "STALE_REVIEWS",
    "INVALID_OPTION_PLAN",
)


class KommunMealOrchestrationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


@dataclass(frozen=True, slots=True)
class KommunMealDestinationResult:
    destination_id: str
    display_name: str
    baseline_quantity: int
    selected_option_id: str | None
    choice_source: str


@dataclass(frozen=True, slots=True)
class KommunMealOptionResult:
    option_id: str
    display_title: str
    assigned_destination_ids: tuple[str, ...]
    assigned_destination_count: int
    has_demand: bool
    requires_review: bool
    review_state: str | None
    review_is_stale: bool
    blockers: tuple[MealBlockerCode, ...]
    planning_slice: PlanningSlice | None
    plan_result: PlanResult | None
    acceptance_issues: tuple[ProductionAcceptanceIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class KommunMealOrchestrationResult:
    tenant_id: int
    site_id: str
    service_date: str
    meal: str
    publication_identity: Product2Page2PublicationIdentity | None
    options: tuple[KommunMealOptionResult, ...]
    unassigned_destinations: tuple[KommunMealDestinationResult, ...]
    blockers: tuple[MealBlockerCode, ...]
    ready: bool


def _normalize_tenant_id(value: object) -> int:
    tenant_id = int(value)
    if tenant_id <= 0:
        raise KommunMealOrchestrationError("tenant_id_invalid", "tenant_id is invalid")
    return tenant_id


def _normalize_site_id(value: object) -> str:
    site_id = str(value or "").strip()
    if not site_id:
        raise KommunMealOrchestrationError("site_id_missing", "site_id is missing")
    return site_id


def _normalize_service_date(value: object) -> _date:
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise KommunMealOrchestrationError("service_date_missing", "service_date is missing")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:
        raise KommunMealOrchestrationError("service_date_invalid", "service_date is invalid") from exc


def _normalize_meal(value: object) -> str:
    meal = str(value or "").strip().lower()
    if not meal:
        raise KommunMealOrchestrationError("meal_missing", "meal is missing")
    if meal != "lunch":
        raise KommunMealOrchestrationError("meal_unsupported", "only lunch is supported")
    return meal


def _ordered_blockers(*blocker_groups: tuple[MealBlockerCode, ...]) -> tuple[MealBlockerCode, ...]:
    ordered: list[MealBlockerCode] = []
    for blocker in _BLOCKER_ORDER:
        for group in blocker_groups:
            if blocker in group and blocker not in ordered:
                ordered.append(blocker)
    return tuple(ordered)


def _destination_result(destination: Product2Page2DestinationVM) -> KommunMealDestinationResult:
    return KommunMealDestinationResult(
        destination_id=str(destination.destination_id),
        display_name=str(destination.display_name),
        baseline_quantity=int(destination.baseline_quantity),
        selected_option_id=destination.selected_option_id,
        choice_source=str(destination.choice_source),
    )


def _assigned_destinations_for_option(
    *,
    context: Product2Page2PlanningContext,
    option_id: str,
) -> tuple[Product2Page2DestinationVM, ...]:
    return tuple(
        destination
        for destination in context.destinations
        if str(destination.selected_option_id or "") == option_id
    )


def _zero_demand_option_result(
    *,
    option,
    assigned_destination_ids: tuple[str, ...],
) -> KommunMealOptionResult:
    return KommunMealOptionResult(
        option_id=str(option.option_id),
        display_title=str(option.display_title),
        assigned_destination_ids=assigned_destination_ids,
        assigned_destination_count=0,
        has_demand=False,
        requires_review=False,
        review_state=None,
        review_is_stale=False,
        blockers=(),
        planning_slice=None,
        plan_result=None,
    )


def _invalid_option_result(
    *,
    option,
    assigned_destination_ids: tuple[str, ...],
    review_state: str | None,
    review_is_stale: bool,
    blocker: MealBlockerCode,
    acceptance_issues: tuple[ProductionAcceptanceIssue, ...] = (),
) -> KommunMealOptionResult:
    return KommunMealOptionResult(
        option_id=str(option.option_id),
        display_title=str(option.display_title),
        assigned_destination_ids=assigned_destination_ids,
        assigned_destination_count=len(assigned_destination_ids),
        has_demand=bool(assigned_destination_ids),
        requires_review=bool(assigned_destination_ids),
        review_state=review_state,
        review_is_stale=bool(review_is_stale),
        blockers=(blocker,),
        planning_slice=None,
        plan_result=None,
        acceptance_issues=acceptance_issues,
    )


def _ready_option_result(
    *,
    option,
    assigned_destination_ids: tuple[str, ...],
    review_state: str,
    review_is_stale: bool,
    planning_slice: PlanningSlice,
    plan_result: PlanResult,
) -> KommunMealOptionResult:
    return KommunMealOptionResult(
        option_id=str(option.option_id),
        display_title=str(option.display_title),
        assigned_destination_ids=assigned_destination_ids,
        assigned_destination_count=len(assigned_destination_ids),
        has_demand=True,
        requires_review=True,
        review_state=review_state,
        review_is_stale=bool(review_is_stale),
        blockers=(),
        planning_slice=planning_slice,
        plan_result=plan_result,
    )


def _build_empty_or_invalid_result(
    *,
    tenant_id: int,
    site_id: str,
    service_date: _date,
    meal: str,
    context: Product2Page2PlanningContext,
    meal_blockers: tuple[MealBlockerCode, ...],
) -> KommunMealOrchestrationResult:
    unassigned_destinations = tuple(
        _destination_result(destination)
        for destination in context.destinations
        if destination.selected_option_id is None
    )
    return KommunMealOrchestrationResult(
        tenant_id=tenant_id,
        site_id=site_id,
        service_date=service_date.isoformat(),
        meal=meal,
        publication_identity=context.publication_identity,
        options=(),
        unassigned_destinations=unassigned_destinations,
        blockers=meal_blockers,
        ready=not meal_blockers,
    )


def _map_adapter_error_code(code: str) -> MealBlockerCode:
    normalized = str(code or "").strip()
    if normalized in {"option_review_required", "option_review_stale"}:
        return "UNREVIEWED_OPTIONS" if normalized == "option_review_required" else "STALE_REVIEWS"
    return "INVALID_OPTION_PLAN"


def _build_option_result(
    *,
    tenant_id: int,
    site_id: str,
    service_date: _date,
    meal: str,
    option,
    context: Product2Page2PlanningContext,
    review_service: PlanningOptionReviewService,
    blockers: set[MealBlockerCode],
) -> KommunMealOptionResult:
    assigned_destinations = _assigned_destinations_for_option(context=context, option_id=str(option.option_id))
    assigned_destination_ids = tuple(destination.destination_id for destination in assigned_destinations)
    if not assigned_destination_ids:
        return _zero_demand_option_result(option=option, assigned_destination_ids=assigned_destination_ids)

    try:
        review_state = review_service.get_option_review_state(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=service_date,
            meal=meal,
            option_id=str(option.option_id),
        )
    except PlanningOptionReviewError as exc:
        blocker = _map_adapter_error_code(getattr(exc, "args", ("",))[0] if getattr(exc, "args", None) else str(exc))
        blockers.add(blocker)
        return _invalid_option_result(
            option=option,
            assigned_destination_ids=assigned_destination_ids,
            review_state=None,
            review_is_stale=False,
            blocker=blocker,
        )

    if review_state.review_is_stale:
        blockers.add("STALE_REVIEWS")
        return _invalid_option_result(
            option=option,
            assigned_destination_ids=assigned_destination_ids,
            review_state=review_state.review_state,
            review_is_stale=True,
            blocker="STALE_REVIEWS",
        )
    if review_state.review_state == REVIEW_STATE_UNREVIEWED:
        blockers.add("UNREVIEWED_OPTIONS")
        return _invalid_option_result(
            option=option,
            assigned_destination_ids=assigned_destination_ids,
            review_state=review_state.review_state,
            review_is_stale=False,
            blocker="UNREVIEWED_OPTIONS",
        )
    if review_state.review_state not in {REVIEW_STATE_NO_DEVIATIONS, REVIEW_STATE_WITH_DEVIATIONS}:
        blockers.add("INVALID_OPTION_PLAN")
        return _invalid_option_result(
            option=option,
            assigned_destination_ids=assigned_destination_ids,
            review_state=review_state.review_state,
            review_is_stale=review_state.review_is_stale,
            blocker="INVALID_OPTION_PLAN",
        )

    try:
        planning_slice = build_planning_slice_from_option_review(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=service_date,
            meal_key=meal,
            option_id=str(option.option_id),
        )
    except KommunOptionReviewPlanningError as exc:
        blocker = _map_adapter_error_code(getattr(exc, "code", str(exc)))
        blockers.add(blocker)
        return _invalid_option_result(
            option=option,
            assigned_destination_ids=assigned_destination_ids,
            review_state=review_state.review_state,
            review_is_stale=review_state.review_is_stale,
            blocker=blocker,
        )

    request = planning_slice.to_plan_request()
    acceptance = validate_plan_request_for_production(request, expected_unit_ids=assigned_destination_ids)
    if not acceptance.accepted:
        blockers.add("INVALID_OPTION_PLAN")
        return _invalid_option_result(
            option=option,
            assigned_destination_ids=assigned_destination_ids,
            review_state=review_state.review_state,
            review_is_stale=review_state.review_is_stale,
            blocker="INVALID_OPTION_PLAN",
            acceptance_issues=tuple(acceptance.issues),
        )

    plan_result = compute_plan(request)
    return _ready_option_result(
        option=option,
        assigned_destination_ids=assigned_destination_ids,
        review_state=review_state.review_state,
        review_is_stale=review_state.review_is_stale,
        planning_slice=planning_slice,
        plan_result=plan_result,
    )


def run_kommun_meal_orchestration(
    *,
    tenant_id,
    site_id,
    service_date,
    meal: str = "lunch",
) -> KommunMealOrchestrationResult:
    normalized_tenant_id = _normalize_tenant_id(tenant_id)
    normalized_site_id = _normalize_site_id(site_id)
    normalized_service_date = _normalize_service_date(service_date)
    normalized_meal = _normalize_meal(meal)

    try:
        context = build_product2_page2_planning_context(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            service_date=normalized_service_date,
            meal=normalized_meal,
        )
    except Exception as exc:
        raise KommunMealOrchestrationError("context_error", str(exc)) from exc

    if context.publication_identity is None or context.status != "ok":
        meal_blockers: tuple[MealBlockerCode, ...] = ("INVALID_OPTION_PLAN",)
        if any(destination.selected_option_id is None for destination in context.destinations):
            meal_blockers = _ordered_blockers(("UNASSIGNED_DESTINATIONS",), meal_blockers)
        return _build_empty_or_invalid_result(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            service_date=normalized_service_date,
            meal=normalized_meal,
            context=context,
            meal_blockers=meal_blockers,
        )

    review_service = PlanningOptionReviewService()
    meal_blockers: set[MealBlockerCode] = set()
    option_results: list[KommunMealOptionResult] = []

    for option in context.options:
        option_result = _build_option_result(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            service_date=normalized_service_date,
            meal=normalized_meal,
            option=option,
            context=context,
            review_service=review_service,
            blockers=meal_blockers,
        )
        option_results.append(option_result)
        for blocker in option_result.blockers:
            meal_blockers.add(blocker)

    unassigned_destinations = tuple(
        _destination_result(destination)
        for destination in context.destinations
        if destination.selected_option_id is None
    )
    if unassigned_destinations:
        meal_blockers.add("UNASSIGNED_DESTINATIONS")

    ordered_blockers = _ordered_blockers(tuple(meal_blockers))
    return KommunMealOrchestrationResult(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date.isoformat(),
        meal=normalized_meal,
        publication_identity=context.publication_identity,
        options=tuple(option_results),
        unassigned_destinations=unassigned_destinations,
        blockers=ordered_blockers,
        ready=not ordered_blockers,
    )


__all__ = [
    "KommunMealDestinationResult",
    "KommunMealOptionResult",
    "KommunMealOrchestrationError",
    "KommunMealOrchestrationResult",
    "MealBlockerCode",
    "run_kommun_meal_orchestration",
]