from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Literal, Protocol

from ...department_menu_choice_repo import MenuChoiceRepo
from ..day_orchestration import KommunDayBusinessContext


TargetDemandResolutionState = Literal["resolved_positive", "resolved_zero", "unresolved"]


@dataclass(frozen=True, slots=True)
class KommunTargetDemandDestinationResult:
    destination_id: str
    baseline_quantity: int
    resolved_quantity: int | None
    resolution_state: TargetDemandResolutionState
    unresolved_reason: str | None = None


@dataclass(frozen=True, slots=True)
class KommunTargetDemandResult:
    tenant_id: int | str
    site_id: str
    service_date: str
    builder_menu_id: str
    builder_menu_version: int
    builder_menu_row_id: str
    composition_id: str | None
    meal: str
    variant_type: str
    day: str
    text: str
    destination_demands: tuple[KommunTargetDemandDestinationResult, ...]


class KommunDemandTarget(Protocol):
    tenant_id: int | str
    site_id: str
    service_date: str
    builder_menu_id: str
    builder_menu_version: int
    builder_menu_row_id: str
    composition_id: str | None
    meal: str
    variant_type: str
    day: str
    text: str


class KommunTargetDemandResolverError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"{self.code}: {self.message}")


def _normalize_id(value: object) -> str:
    return str(value or "").strip()


def _normalize_service_date(value: object) -> _date:
    if isinstance(value, _date):
        return value
    raw = _normalize_id(value)
    if not raw:
        raise KommunTargetDemandResolverError("service_date_missing", "service_date is required")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:
        raise KommunTargetDemandResolverError("service_date_invalid", "service_date must be ISO format") from exc


def _selected_variant_for_destination(
    *,
    tenant_id: int | str,
    site_id: str,
    department_id: str,
    service_date: _date,
    meal: str,
) -> str | None:
    year, week, weekday = service_date.isocalendar()
    rows = MenuChoiceRepo().list_for_department_week(
        tenant_id=int(tenant_id),
        site_id=site_id,
        department_id=department_id,
        year=year,
        week=week,
    )
    for row in rows:
        if int(row.weekday) == int(weekday) and str(row.meal).strip().lower() == meal:
            return str(row.selected_variant).strip().lower() or None
    return None


def _resolution_result(
    *,
    destination_id: str,
    baseline_quantity: int,
    resolved_quantity: int | None,
    resolution_state: TargetDemandResolutionState,
    unresolved_reason: str | None = None,
) -> KommunTargetDemandDestinationResult:
    return KommunTargetDemandDestinationResult(
        destination_id=destination_id,
        baseline_quantity=int(baseline_quantity),
        resolved_quantity=int(resolved_quantity) if resolved_quantity is not None else None,
        resolution_state=resolution_state,
        unresolved_reason=unresolved_reason,
    )


def resolve_kommun_target_demand(
    *,
    context: KommunDayBusinessContext,
    target: KommunDemandTarget,
) -> KommunTargetDemandResult:
    if _normalize_id(context.tenant_id) != _normalize_id(target.tenant_id):
        raise KommunTargetDemandResolverError("context_mismatch", "tenant_id does not match target")
    if _normalize_id(context.site_id) != _normalize_id(target.site_id):
        raise KommunTargetDemandResolverError("context_mismatch", "site_id does not match target")
    if _normalize_id(context.service_date) != _normalize_id(target.service_date):
        raise KommunTargetDemandResolverError("context_mismatch", "service_date does not match target")

    service_date_value = _normalize_service_date(context.service_date)
    meal = _normalize_id(target.meal).lower()
    variant_type = _normalize_id(target.variant_type).lower()

    destination_demands: list[KommunTargetDemandDestinationResult] = []
    for department in context.departments:
        destination_id = _normalize_id(department.department_id)
        if meal == "dinner":
            baseline_quantity = int(context.dinner_baselines.get(destination_id, 0))
            resolved_quantity = baseline_quantity
            state: TargetDemandResolutionState = "resolved_positive" if baseline_quantity > 0 else "resolved_zero"
            destination_demands.append(
                _resolution_result(
                    destination_id=destination_id,
                    baseline_quantity=baseline_quantity,
                    resolved_quantity=resolved_quantity,
                    resolution_state=state,
                )
            )
            continue

        if meal != "lunch":
            raise KommunTargetDemandResolverError("meal_unsupported", f"unsupported meal for target demand: {meal or '<empty>'}")

        lunch_baseline = int(context.lunch_baselines.get(destination_id, 0))
        if variant_type == "dessert":
            resolved_quantity = lunch_baseline
            state = "resolved_positive" if lunch_baseline > 0 else "resolved_zero"
            destination_demands.append(
                _resolution_result(
                    destination_id=destination_id,
                    baseline_quantity=lunch_baseline,
                    resolved_quantity=resolved_quantity,
                    resolution_state=state,
                )
            )
            continue

        if variant_type not in {"alt1", "alt2"}:
            raise KommunTargetDemandResolverError("variant_unsupported", f"unsupported lunch target variant: {variant_type or '<empty>'}")

        selected_variant = _selected_variant_for_destination(
            tenant_id=target.tenant_id,
            site_id=target.site_id,
            department_id=destination_id,
            service_date=service_date_value,
            meal=meal,
        )
        if selected_variant is None:
            destination_demands.append(
                _resolution_result(
                    destination_id=destination_id,
                    baseline_quantity=lunch_baseline,
                    resolved_quantity=None,
                    resolution_state="unresolved",
                    unresolved_reason="menu_choice_missing",
                )
            )
            continue

        if selected_variant == variant_type:
            resolved_quantity = lunch_baseline
            state = "resolved_positive" if lunch_baseline > 0 else "resolved_zero"
            destination_demands.append(
                _resolution_result(
                    destination_id=destination_id,
                    baseline_quantity=lunch_baseline,
                    resolved_quantity=resolved_quantity,
                    resolution_state=state,
                )
            )
            continue

        destination_demands.append(
            _resolution_result(
                destination_id=destination_id,
                baseline_quantity=lunch_baseline,
                resolved_quantity=0,
                resolution_state="resolved_zero",
            )
        )

    return KommunTargetDemandResult(
        tenant_id=context.tenant_id,
        site_id=context.site_id,
        service_date=context.service_date,
        builder_menu_id=str(target.builder_menu_id),
        builder_menu_version=int(target.builder_menu_version),
        builder_menu_row_id=str(target.builder_menu_row_id),
        composition_id=str(target.composition_id) if target.composition_id is not None else None,
        meal=meal,
        variant_type=variant_type,
        day=str(target.day),
        text=str(target.text),
        destination_demands=tuple(destination_demands),
    )


__all__ = [
    "KommunTargetDemandDestinationResult",
    "KommunTargetDemandResolutionState",
    "KommunTargetDemandResolverError",
    "KommunTargetDemandResult",
    "resolve_kommun_target_demand",
]
