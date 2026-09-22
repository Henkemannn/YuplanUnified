from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date as _date, datetime as _datetime
from typing import Any, NoReturn

from ...planning_option_review import ADAPTATION_REQUIRED, NO_ADAPTATION_REQUIRED, PlanningOptionReviewService
from ...planera_product2_page2_context import (
    Product2Page2ContextError,
    Product2Page2DestinationVM,
    Product2Page2RequirementGroupVM,
    build_product2_page2_planning_context,
)
from ..domain import Deviation, PlanningSlice, UnitInput


class KommunOptionReviewPlanningError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


@dataclass(frozen=True, slots=True)
class _OptionReviewScope:
    tenant_id: int
    site_id: str
    service_date: _date
    meal_key: str
    option_id: str
    context: Any
    review_state: Any
    publication_identity: Any
    assigned_destinations: tuple[Product2Page2DestinationVM, ...]
    relevant_groups: tuple[Product2Page2RequirementGroupVM, ...]


def _fail(code: str, message: str) -> NoReturn:
    raise KommunOptionReviewPlanningError(code, message)


def _normalize_tenant_id(value: object) -> int:
    tenant_id = int(value)
    if tenant_id <= 0:
        _fail("tenant_id_invalid", "tenant_id is invalid")
    return tenant_id


def _normalize_site_id(value: object) -> str:
    site_id = str(value or "").strip()
    if not site_id:
        _fail("site_id_missing", "site_id is missing")
    return site_id


def _normalize_service_date(value: object) -> _date:
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        _fail("service_date_missing", "service_date is missing")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:  # pragma: no cover - defensive normalization
        raise KommunOptionReviewPlanningError("service_date_invalid", "service_date is invalid") from exc


def _normalize_meal_key(value: object) -> str:
    meal_key = str(value or "").strip().lower()
    if not meal_key:
        _fail("meal_key_missing", "meal_key is missing")
    return meal_key


def _normalize_option_id(value: object) -> str:
    option_id = str(value or "").strip()
    if not option_id:
        _fail("option_id_missing", "option_id is missing")
    return option_id


def _normalize_requirement_keys(requirements: Iterable[Any]) -> list[str]:
    keys: list[str] = []
    for requirement in requirements:
        requirement_key = str(getattr(requirement, "requirement_key", None) or "").strip()
        semantics = str(getattr(requirement, "semantics", None) or "").strip().lower()
        if not requirement_key:
            _fail("requirement_key_missing", "requirement_key is missing")
        if semantics != "atomic":
            _fail("requirement_semantics_invalid", "requirement semantics must be atomic")
        keys.append(requirement_key)

    if not keys:
        _fail("requirement_group_empty", "requirement group has no requirements")

    sorted_keys = sorted(set(keys))
    if len(sorted_keys) != len(keys):
        # duplicated requirement keys within one cohort are suspicious and should be blocked
        _fail("requirement_key_duplicate", "requirement keys must be unique within a cohort")
    return sorted_keys


def _build_scope(
    *,
    tenant_id: int,
    site_id: str,
    service_date: _date,
    meal_key: str,
    option_id: str,
) -> _OptionReviewScope:
    try:
        context = build_product2_page2_planning_context(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=service_date,
            meal=meal_key,
        )
    except Exception as exc:  # pragma: no cover - defensive adapter boundary
        raise KommunOptionReviewPlanningError(getattr(exc, "code", str(exc)), str(exc)) from exc

    if context.publication_identity is None or context.status != "ok":
        _fail("option_not_published", "option is not published")

    publication_identity = context.publication_identity
    if publication_identity is None:
        _fail("option_not_published", "option is not published")

    if not any(str(option.option_id) == option_id for option in context.options):
        _fail("option_not_published", "option is not published")

    assigned_destinations = tuple(
        destination
        for destination in context.destinations
        if str(destination.selected_option_id or "") == option_id
    )
    relevant_groups = tuple(
        group for group in context.requirement_groups if str(group.destination_id) in {destination.destination_id for destination in assigned_destinations}
    )
    return _OptionReviewScope(
        tenant_id=tenant_id,
        site_id=site_id,
        service_date=service_date,
        meal_key=meal_key,
        option_id=option_id,
        context=context,
        review_state=None,
        publication_identity=publication_identity,
        assigned_destinations=assigned_destinations,
        relevant_groups=relevant_groups,
    )


def _build_decision_map(review_state) -> dict[tuple[str, str], str]:
    decision_map: dict[tuple[str, str], str] = {}
    for decision in review_state.decisions:
        key = (str(decision.destination_id), str(decision.requirement_group_id))
        if key in decision_map:
            _fail("duplicate_decision", "duplicate review decision")
        decision_map[key] = str(decision.decision)
    return decision_map


def _build_planning_slice(
    *,
    tenant_id: int,
    site_id: str,
    service_date: _date,
    meal_key: str,
    option_id: str,
    context: dict[str, Any] | None,
    scope: _OptionReviewScope,
) -> PlanningSlice:
    current_groups_by_key: dict[tuple[str, str], Product2Page2RequirementGroupVM] = {}
    current_groups_by_destination: dict[str, list[Product2Page2RequirementGroupVM]] = {
        destination.destination_id: [] for destination in scope.assigned_destinations
    }
    for group in scope.relevant_groups:
        if str(group.destination_id) not in current_groups_by_destination:
            continue
        key = (str(group.destination_id), str(group.requirement_group_id))
        current_groups_by_key[key] = group
        current_groups_by_destination.setdefault(str(group.destination_id), []).append(group)

    for group in current_groups_by_key.values():
        _normalize_requirement_keys(group.requirements)

    review_service = PlanningOptionReviewService()
    try:
        review_state = review_service.get_option_review_state(
            tenant_id=tenant_id,
            site_id=site_id,
            service_date=service_date,
            meal=meal_key,
            option_id=option_id,
        )
    except Exception as exc:  # pragma: no cover - defensive adapter boundary
        raise KommunOptionReviewPlanningError(getattr(exc, "code", str(exc)), str(exc)) from exc

    if review_state.review_is_stale:
        _fail("option_review_stale", "option review is stale")
    if review_state.review_id is None or review_state.completed_at is None:
        _fail("option_review_required", "option review is required")
    if review_state.review_state not in {"REVIEWED_NO_DEVIATIONS", "REVIEWED_WITH_DEVIATIONS"}:
        _fail("option_review_required", "option review is required")

    assigned_destination_ids = {destination.destination_id for destination in scope.assigned_destinations}
    decision_map = _build_decision_map(review_state)
    current_keys = set(current_groups_by_key)
    decision_keys = set(decision_map)

    if decision_keys - current_keys:
        _fail("irrelevant_decision", "decision references a non-current group")
    if current_keys - decision_keys:
        _fail("missing_decision", "current relevant group is missing an explicit decision")

    for destination_id in sorted(current_groups_by_destination):
        destination = next((item for item in scope.assigned_destinations if item.destination_id == destination_id), None)
        if destination is None:
            _fail("decision_destination_not_assigned", "destination is not assigned to this option")
        cohort_total = sum(group.effective_quantity for group in current_groups_by_destination[destination_id])
        if cohort_total > destination.baseline_quantity:
            _fail("cohort_quantity_exceeds_baseline", "cohort quantity exceeds destination baseline")

    units = tuple(
        UnitInput(unit_id=destination.destination_id, baseline_total=int(destination.baseline_quantity))
        for destination in sorted(scope.assigned_destinations, key=lambda item: item.destination_id)
    )
    baseline_total = sum(unit.baseline_total for unit in units)

    deviations: list[Deviation] = []
    requirement_group_refs: list[dict[str, object]] = []
    for destination in sorted(scope.assigned_destinations, key=lambda item: item.destination_id):
        destination_groups = sorted(
            current_groups_by_destination.get(destination.destination_id, []),
            key=lambda item: item.requirement_group_id,
        )
        for group in destination_groups:
            decision = decision_map[(destination.destination_id, group.requirement_group_id)]
            if decision == NO_ADAPTATION_REQUIRED:
                continue
            if decision != ADAPTATION_REQUIRED:
                _fail("decision_invalid", "decision value is invalid")

            category_keys = _normalize_requirement_keys(group.requirements)
            quantity = int(group.effective_quantity)
            if quantity <= 0:
                _fail("cohort_quantity_invalid", "cohort quantity must be positive")

            deviations.append(
                Deviation(
                    form="unspecified",
                    category_keys=category_keys,
                    quantity=quantity,
                    unit_id=destination.destination_id,
                )
            )
            requirement_group_refs.append(
                {
                    "requirement_group_id": group.requirement_group_id,
                    "destination_id": destination.destination_id,
                    "unit_id": destination.destination_id,
                    "category_keys": category_keys,
                    "quantity": quantity,
                }
            )

    planning_context = dict(context) if isinstance(context, dict) else {}
    planning_context.update(
        {
            "source": "planning_option_review",
            "tenant_id": tenant_id,
            "site_id": site_id,
            "date": service_date.isoformat(),
            "meal_key": meal_key,
            "builder_menu_id": str(scope.publication_identity.builder_menu_id),
            "builder_menu_version": int(scope.publication_identity.builder_menu_version),
            "builder_menu_row_id": option_id,
            "option_id": option_id,
            "review_id": int(review_state.review_id),
            "review_basis_hash": str(review_state.review_basis_hash),
            "compatibility_source_precision": "planning_option_review",
            "compatibility_status": "resolved",
            "requirement_group_refs": requirement_group_refs,
        }
    )

    return PlanningSlice(
        baseline=baseline_total,
        units=units,
        deviations=tuple(deviations),
        context=planning_context,
        warnings=(),
        compatibility_status="resolved",
    )


def build_planning_slice_from_option_review(
    *,
    tenant_id,
    site_id,
    service_date,
    meal_key,
    option_id,
    context: dict[str, Any] | None = None,
) -> PlanningSlice:
    normalized_tenant_id = _normalize_tenant_id(tenant_id)
    normalized_site_id = _normalize_site_id(site_id)
    normalized_service_date = _normalize_service_date(service_date)
    normalized_meal_key = _normalize_meal_key(meal_key)
    normalized_option_id = _normalize_option_id(option_id)

    scope = _build_scope(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date,
        meal_key=normalized_meal_key,
        option_id=normalized_option_id,
    )
    return _build_planning_slice(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date,
        meal_key=normalized_meal_key,
        option_id=normalized_option_id,
        context=context,
        scope=scope,
    )


__all__ = [
    "KommunOptionReviewPlanningError",
    "build_planning_slice_from_option_review",
]