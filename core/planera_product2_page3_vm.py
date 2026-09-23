from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from sqlalchemy import text

from .db import get_session, get_site_tenant
from .planera_product2_page2_context import Product2Page2PlanningContext, build_product2_page2_planning_context
from .planera_v2.meal_orchestration import (
    KommunMealDestinationResult,
    KommunMealOptionResult,
    KommunMealOrchestrationResult,
    run_kommun_meal_orchestration,
)


class Product2Page3VmError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Product2Page3DepartmentQuantityVM:
    destination_id: str
    display_name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class Product2Page3SpecialCohortVM:
    label: str
    quantity: int
    department_quantities: tuple[Product2Page3DepartmentQuantityVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3OptionVM:
    option_id: str
    display_label: str
    display_title: str
    has_demand: bool
    status_label: str | None
    blockers: tuple[str, ...]
    baseline_total: int | None
    normal_total: int | None
    special_total: int | None
    normal_department_rows: tuple[Product2Page3DepartmentQuantityVM, ...]
    special_cohorts: tuple[Product2Page3SpecialCohortVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3DestinationVM:
    destination_id: str
    display_name: str
    baseline_quantity: int


@dataclass(frozen=True, slots=True)
class Product2Page3VM:
    tenant_id: int
    site_id: str
    site_name: str
    service_date: str
    service_date_label: str
    meal: str
    meal_label: str
    ready: bool
    ready_label: str
    blockers: tuple[str, ...]
    blocker_messages: tuple[str, ...]
    page2_url: str
    publication_identity: object | None
    options: tuple[Product2Page3OptionVM, ...]
    unassigned_destinations: tuple[Product2Page3DestinationVM, ...]


def _normalize_tenant_id(value: object) -> int:
    try:
        tenant_id = int(value)
    except Exception as exc:
        raise Product2Page3VmError("tenant_id_missing") from exc
    if tenant_id <= 0:
        raise Product2Page3VmError("tenant_id_missing")
    return tenant_id


def _normalize_site_id(value: object) -> str:
    site_id = str(value or "").strip()
    if not site_id:
        raise Product2Page3VmError("site_id_missing")
    return site_id


def _normalize_service_date(value: object) -> _date:
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise Product2Page3VmError("service_date_missing")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:
        raise Product2Page3VmError("service_date_invalid") from exc


def _normalize_meal(value: object) -> str:
    meal = str(value or "").strip().lower()
    if meal != "lunch":
        raise Product2Page3VmError("meal_unsupported")
    return meal


def _format_service_date_label(service_date: _date) -> str:
    day_names = {
        0: "måndag",
        1: "tisdag",
        2: "onsdag",
        3: "torsdag",
        4: "fredag",
        5: "lördag",
        6: "söndag",
    }
    month_names = {
        1: "januari",
        2: "februari",
        3: "mars",
        4: "april",
        5: "maj",
        6: "juni",
        7: "juli",
        8: "augusti",
        9: "september",
        10: "oktober",
        11: "november",
        12: "december",
    }
    weekday = service_date.weekday()
    return f"{day_names.get(weekday, '')} {service_date.day} {month_names.get(service_date.month, '')} {service_date.year}".strip()


def _load_site_name(*, tenant_id: int, site_id: str) -> str:
    site_tenant_id = get_site_tenant(site_id)
    if site_tenant_id is None or int(site_tenant_id) != int(tenant_id):
        raise Product2Page3VmError("site_tenant_mismatch")
    db = get_session()
    try:
        row = db.execute(text("SELECT name FROM sites WHERE id=:site_id"), {"site_id": site_id}).fetchone()
    finally:
        db.close()
    if row is None:
        raise Product2Page3VmError("site_not_found")
    site_name = str(row[0] or "").strip()
    if not site_name:
        raise Product2Page3VmError("site_name_missing")
    return site_name


def _build_requirement_name_map(context: Product2Page2PlanningContext) -> dict[str, str]:
    requirement_names: dict[str, str] = {}
    for group in context.requirement_groups:
        for requirement in group.requirements:
            requirement_key = str(requirement.requirement_key or "").strip()
            requirement_name = str(requirement.name or "").strip()
            if not requirement_key:
                continue
            if not requirement_name:
                raise Product2Page3VmError(f"requirement_name_missing:{requirement_key}")
            existing = requirement_names.get(requirement_key)
            if existing is not None and existing != requirement_name:
                raise Product2Page3VmError(f"requirement_name_conflict:{requirement_key}")
            requirement_names[requirement_key] = requirement_name
    return requirement_names


def _build_destination_name_map(context: Product2Page2PlanningContext) -> dict[str, Product2Page3DestinationVM]:
    destination_map: dict[str, Product2Page3DestinationVM] = {}
    for destination in context.destinations:
        destination_id = str(destination.destination_id)
        display_name = str(destination.display_name or "").strip()
        if not display_name:
            raise Product2Page3VmError(f"destination_name_missing:{destination_id}")
        destination_map[destination_id] = Product2Page3DestinationVM(
            destination_id=destination_id,
            display_name=display_name,
            baseline_quantity=int(destination.baseline_quantity),
        )
    return destination_map


def _parse_combination_key(key: str) -> tuple[str, tuple[str, ...]]:
    parts = str(key or "").split("__")
    if not parts:
        raise Product2Page3VmError("combination_key_missing")
    form = parts[0].strip()
    categories = tuple(part.strip() for part in parts[1:] if part.strip())
    if not categories:
        raise Product2Page3VmError(f"combination_categories_missing:{key}")
    return form, categories


def _combo_label_from_key(key: str, requirement_name_map: dict[str, str]) -> str:
    _form, category_keys = _parse_combination_key(key)
    labels: list[str] = []
    for category_key in category_keys:
        label = requirement_name_map.get(category_key)
        if not label:
            raise Product2Page3VmError(f"requirement_label_missing:{category_key}")
        if label not in labels:
            labels.append(label)
    return " + ".join(labels)


def _department_rows_for_combination(
    *,
    option_result: KommunMealOptionResult,
    combination_key: str,
    destination_map: dict[str, Product2Page3DestinationVM],
) -> tuple[Product2Page3DepartmentQuantityVM, ...]:
    rows: list[Product2Page3DepartmentQuantityVM] = []
    for destination_id, breakdown in option_result.plan_result.per_unit_breakdown.items():
        quantity = int(breakdown.per_combination.get(combination_key, 0))
        if quantity <= 0:
            continue
        destination = destination_map.get(destination_id)
        if destination is None:
            raise Product2Page3VmError(f"destination_missing:{destination_id}")
        rows.append(
            Product2Page3DepartmentQuantityVM(
                destination_id=destination.destination_id,
                display_name=destination.display_name,
                quantity=quantity,
            )
        )
    return tuple(rows)


def _normal_department_rows(
    *,
    option_result: KommunMealOptionResult,
    destination_map: dict[str, Product2Page3DestinationVM],
) -> tuple[Product2Page3DepartmentQuantityVM, ...]:
    rows: list[Product2Page3DepartmentQuantityVM] = []
    for destination_id, breakdown in option_result.plan_result.per_unit_breakdown.items():
        destination = destination_map.get(destination_id)
        if destination is None:
            raise Product2Page3VmError(f"destination_missing:{destination_id}")
        rows.append(
            Product2Page3DepartmentQuantityVM(
                destination_id=destination.destination_id,
                display_name=destination.display_name,
                quantity=int(breakdown.normal_total),
            )
        )
    return tuple(rows)


def _option_status_label(option: KommunMealOptionResult) -> str | None:
    if not option.has_demand:
        return "Inga avdelningar har valt denna rätt."
    if not option.plan_result:
        if "UNREVIEWED_OPTIONS" in option.blockers:
            return "Granskning krävs"
        if "STALE_REVIEWS" in option.blockers:
            return "Granskningen behöver göras om"
        if "INVALID_OPTION_PLAN" in option.blockers:
            return "Produktionsunderlag kan inte beräknas"
    return None


def _build_option_vm(
    *,
    option: KommunMealOptionResult,
    context_option,
    destination_map: dict[str, Product2Page3DestinationVM],
    requirement_name_map: dict[str, str],
) -> Product2Page3OptionVM:
    status_label = _option_status_label(option)
    if option.plan_result is None:
        return Product2Page3OptionVM(
            option_id=option.option_id,
            display_label=str(getattr(context_option, "display_label", "")).strip(),
            display_title=option.display_title,
            has_demand=option.has_demand,
            status_label=status_label,
            blockers=option.blockers,
            baseline_total=None,
            normal_total=None,
            special_total=None,
            normal_department_rows=(),
            special_cohorts=(),
        )

    special_cohorts: list[Product2Page3SpecialCohortVM] = []
    for combination_key, quantity in option.plan_result.per_combination.items():
        display_label = _combo_label_from_key(combination_key, requirement_name_map)
        department_rows = _department_rows_for_combination(
            option_result=option,
            combination_key=combination_key,
            destination_map=destination_map,
        )
        special_cohorts.append(
            Product2Page3SpecialCohortVM(
                label=display_label,
                quantity=int(quantity),
                department_quantities=department_rows,
            )
        )

    return Product2Page3OptionVM(
        option_id=option.option_id,
        display_label=str(getattr(context_option, "display_label", "")).strip(),
        display_title=option.display_title,
        has_demand=option.has_demand,
        status_label=status_label,
        blockers=option.blockers,
        baseline_total=int(option.plan_result.totals.baseline_total),
        normal_total=int(option.plan_result.totals.normal_total),
        special_total=int(option.plan_result.totals.deviation_total),
        normal_department_rows=_normal_department_rows(option_result=option, destination_map=destination_map),
        special_cohorts=tuple(special_cohorts),
    )


def build_product2_page3_vm(
    *,
    tenant_id,
    site_id,
    service_date,
    meal,
) -> Product2Page3VM:
    normalized_tenant_id = _normalize_tenant_id(tenant_id)
    normalized_site_id = _normalize_site_id(site_id)
    normalized_service_date = _normalize_service_date(service_date)
    normalized_meal = _normalize_meal(meal)

    site_name = _load_site_name(tenant_id=normalized_tenant_id, site_id=normalized_site_id)
    page2_context = build_product2_page2_planning_context(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date,
        meal=normalized_meal,
    )
    meal_result = run_kommun_meal_orchestration(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date,
        meal=normalized_meal,
    )

    requirement_name_map = _build_requirement_name_map(page2_context)
    destination_map = _build_destination_name_map(page2_context)
    option_result_by_id = {option.option_id: option for option in meal_result.options}
    options: list[Product2Page3OptionVM] = []

    for context_option in page2_context.options:
        option_result = option_result_by_id.get(str(context_option.option_id))
        if option_result is None:
            raise Product2Page3VmError(f"missing_option_result:{context_option.option_id}")
        options.append(
            _build_option_vm(
                option=option_result,
                context_option=context_option,
                destination_map=destination_map,
                requirement_name_map=requirement_name_map,
            )
        )

    unassigned_destinations: list[Product2Page3DestinationVM] = []
    for destination in meal_result.unassigned_destinations:
        mapped = destination_map.get(destination.destination_id)
        if mapped is None:
            raise Product2Page3VmError(f"missing_unassigned_destination:{destination.destination_id}")
        unassigned_destinations.append(mapped)

    blocker_messages = []
    if "UNASSIGNED_DESTINATIONS" in meal_result.blockers and unassigned_destinations:
        blocker_messages.append("Följande avdelningar saknar menyval")
    if "UNREVIEWED_OPTIONS" in meal_result.blockers:
        blocker_messages.append("Granskning krävs för att slutföra produktionsunderlaget")
    if "STALE_REVIEWS" in meal_result.blockers:
        blocker_messages.append("Vissa granskningar behöver göras om")
    if "INVALID_OPTION_PLAN" in meal_result.blockers:
        blocker_messages.append("Ett eller flera produktionsunderlag kan inte beräknas")

    return Product2Page3VM(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        site_name=site_name,
        service_date=normalized_service_date.isoformat(),
        service_date_label=_format_service_date_label(normalized_service_date),
        meal=normalized_meal,
        meal_label="Lunch" if normalized_meal == "lunch" else normalized_meal.capitalize(),
        ready=bool(meal_result.ready),
        ready_label="Produktionsunderlaget är klart" if meal_result.ready else "Produktionsunderlaget är inte komplett",
        blockers=meal_result.blockers,
        blocker_messages=tuple(blocker_messages),
        page2_url=f"/ui/kitchen/planering/day?ui=product2&site_id={normalized_site_id}&date={normalized_service_date.isoformat()}&meal={normalized_meal}",
        publication_identity=meal_result.publication_identity,
        options=tuple(options),
        unassigned_destinations=tuple(unassigned_destinations),
    )


__all__ = [
    "Product2Page3DepartmentQuantityVM",
    "Product2Page3OptionVM",
    "Product2Page3DestinationVM",
    "Product2Page3SpecialCohortVM",
    "Product2Page3VM",
    "Product2Page3VmError",
    "build_product2_page3_vm",
]