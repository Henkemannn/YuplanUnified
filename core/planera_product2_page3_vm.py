from __future__ import annotations

from dataclasses import dataclass, field
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
class Product2Page3NormalMatrixCellVM:
    option_id: str
    quantity: int | None
    display_value: str


@dataclass(frozen=True, slots=True)
class Product2Page3NormalMatrixColumnVM:
    option_id: str
    display_title: str
    total: int | None
    display_total: str


@dataclass(frozen=True, slots=True)
class Product2Page3NormalMatrixRowVM:
    destination_id: str
    display_name: str
    cells: tuple[Product2Page3NormalMatrixCellVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3NormalMatrixVM:
    columns: tuple[Product2Page3NormalMatrixColumnVM, ...]
    rows: tuple[Product2Page3NormalMatrixRowVM, ...]
    totals: tuple[Product2Page3NormalMatrixColumnVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3SpecialCohortVM:
    label: str
    quantity: int
    department_quantities: tuple[Product2Page3DepartmentQuantityVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3SpecialDishVM:
    option_id: str
    display_title: str
    quantity: int
    department_quantities: tuple[Product2Page3DepartmentQuantityVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3SpecialProductionGroupVM:
    combination_key: str
    label: str
    quantity: int
    dishes: tuple[Product2Page3SpecialDishVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3SpecialDestinationDishVM:
    option_id: str
    display_title: str
    quantity: int


@dataclass(frozen=True, slots=True)
class Product2Page3SpecialDestinationRowVM:
    combination_key: str
    label: str
    quantity: int
    dishes: tuple[Product2Page3SpecialDestinationDishVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page3SpecialDestinationGroupVM:
    destination_id: str
    display_name: str
    rows: tuple[Product2Page3SpecialDestinationRowVM, ...]


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
    view: str = "overview"
    special_view: str = "production"
    overview_options: tuple[Product2Page3OptionVM, ...] = ()
    normal_matrix: Product2Page3NormalMatrixVM | None = None
    special_production_groups: tuple[Product2Page3SpecialProductionGroupVM, ...] = ()
    special_destination_groups: tuple[Product2Page3SpecialDestinationGroupVM, ...] = ()
    navigation_urls: dict[str, str] = field(default_factory=dict)
    special_navigation_urls: dict[str, str] = field(default_factory=dict)
    service_date_compact_label: str = ""


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


def _format_service_date_compact_label(service_date: _date) -> str:
    day_names = {
        0: "mån",
        1: "tis",
        2: "ons",
        3: "tors",
        4: "fre",
        5: "lör",
        6: "sön",
    }
    month_names = {
        1: "jan",
        2: "feb",
        3: "mar",
        4: "apr",
        5: "maj",
        6: "jun",
        7: "jul",
        8: "aug",
        9: "sep",
        10: "okt",
        11: "nov",
        12: "dec",
    }
    weekday = service_date.weekday()
    return f"{day_names.get(weekday, '')} {service_date.day} {month_names.get(service_date.month, '')}".strip()


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


def _display_matrix_quantity(value: int | None) -> str:
    if value is None or int(value) <= 0:
        return "—"
    return str(int(value))


def _display_summary_quantity(value: int | None) -> str:
    if value is None:
        return "—"
    return str(int(value))


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


def _build_normal_matrix(
    *,
    options: tuple[KommunMealOptionResult, ...],
    context_options,
    destination_map: dict[str, Product2Page3DestinationVM],
) -> Product2Page3NormalMatrixVM:
    option_results = {option.option_id: option for option in options}
    columns: list[Product2Page3NormalMatrixColumnVM] = []
    rows: list[Product2Page3NormalMatrixRowVM] = []

    for context_option in context_options:
        option_result = option_results.get(str(context_option.option_id))
        if option_result is None or option_result.plan_result is None:
            columns.append(
                Product2Page3NormalMatrixColumnVM(
                    option_id=str(context_option.option_id),
                    display_title=str(getattr(context_option, "display_title", "")).strip(),
                    total=None,
                    display_total="—",
                )
            )
            continue
        total = int(option_result.plan_result.totals.normal_total)
        columns.append(
            Product2Page3NormalMatrixColumnVM(
                option_id=option_result.option_id,
                display_title=option_result.display_title,
                total=total,
                display_total=_display_summary_quantity(total),
            )
        )

    for destination in destination_map.values():
        cells: list[Product2Page3NormalMatrixCellVM] = []
        for context_option in context_options:
            option_result = option_results.get(str(context_option.option_id))
            quantity: int | None = None
            if option_result is not None and option_result.plan_result is not None:
                breakdown = option_result.plan_result.per_unit_breakdown.get(destination.destination_id)
                if breakdown is not None:
                    quantity = int(breakdown.normal_total)
            cells.append(
                Product2Page3NormalMatrixCellVM(
                    option_id=str(context_option.option_id),
                    quantity=quantity,
                    display_value=_display_matrix_quantity(quantity),
                )
            )
        rows.append(
            Product2Page3NormalMatrixRowVM(
                destination_id=destination.destination_id,
                display_name=destination.display_name,
                cells=tuple(cells),
            )
        )

    return Product2Page3NormalMatrixVM(columns=tuple(columns), rows=tuple(rows), totals=tuple(columns))


def _build_special_production_groups(
    *,
    options: tuple[KommunMealOptionResult, ...],
    context_options,
    destination_map: dict[str, Product2Page3DestinationVM],
    requirement_name_map: dict[str, str],
) -> tuple[Product2Page3SpecialProductionGroupVM, ...]:
    option_results = {option.option_id: option for option in options}
    grouped: dict[str, dict[str, object]] = {}
    group_order: list[str] = []
    option_order = {str(context_option.option_id): index for index, context_option in enumerate(context_options)}

    for context_option in context_options:
        option_result = option_results.get(str(context_option.option_id))
        if option_result is None or option_result.plan_result is None:
            continue
        for combination_key, quantity in option_result.plan_result.per_combination.items():
            if int(quantity) <= 0:
                continue
            label = _combo_label_from_key(combination_key, requirement_name_map)
            group = grouped.get(combination_key)
            if group is None:
                group = {
                    "combination_key": combination_key,
                    "label": label,
                    "quantity": 0,
                    "dishes": {},
                }
                grouped[combination_key] = group
                group_order.append(combination_key)
            group["quantity"] = int(group["quantity"]) + int(quantity)
            dishes: dict[str, dict[str, object]] = group["dishes"]  # type: ignore[assignment]
            dish = dishes.get(option_result.option_id)
            if dish is None:
                dish = {
                    "option_id": option_result.option_id,
                    "display_title": option_result.display_title,
                    "quantity": 0,
                    "department_quantities": [],
                    "order": option_order.get(option_result.option_id, 0),
                }
                dishes[option_result.option_id] = dish
            dish["quantity"] = int(dish["quantity"]) + int(quantity)
            department_quantities = _department_rows_for_combination(
                option_result=option_result,
                combination_key=combination_key,
                destination_map=destination_map,
            )
            existing_rows = list(dish["department_quantities"])  # type: ignore[index]
            existing_rows.extend(department_quantities)
            dish["department_quantities"] = existing_rows

    groups: list[Product2Page3SpecialProductionGroupVM] = []
    for combination_key in sorted(group_order, key=lambda key: (-(int(grouped[key]["quantity"])), str(grouped[key]["label"]))):
        group = grouped[combination_key]
        dishes_map: dict[str, dict[str, object]] = group["dishes"]  # type: ignore[assignment]
        dishes: list[Product2Page3SpecialDishVM] = []
        for dish in sorted(dishes_map.values(), key=lambda item: (int(item.get("order", 0)), str(item.get("display_title", "")))):
            rows = tuple(dish.get("department_quantities") or ())
            dishes.append(
                Product2Page3SpecialDishVM(
                    option_id=str(dish.get("option_id", "")),
                    display_title=str(dish.get("display_title", "")),
                    quantity=int(dish.get("quantity", 0)),
                    department_quantities=rows,
                )
            )
        groups.append(
            Product2Page3SpecialProductionGroupVM(
                combination_key=str(group["combination_key"]),
                label=str(group["label"]),
                quantity=int(group["quantity"]),
                dishes=tuple(dishes),
            )
        )
    return tuple(groups)


def _build_special_destination_groups(
    *,
    options: tuple[KommunMealOptionResult, ...],
    context_options,
    destination_map: dict[str, Product2Page3DestinationVM],
    requirement_name_map: dict[str, str],
) -> tuple[Product2Page3SpecialDestinationGroupVM, ...]:
    option_results = {option.option_id: option for option in options}
    destination_groups: dict[str, dict[str, object]] = {}
    destination_order = {destination_id: index for index, destination_id in enumerate(destination_map.keys())}
    option_order = {str(context_option.option_id): index for index, context_option in enumerate(context_options)}

    for context_option in context_options:
        option_result = option_results.get(str(context_option.option_id))
        if option_result is None or option_result.plan_result is None:
            continue
        for destination_id, breakdown in option_result.plan_result.per_unit_breakdown.items():
            destination = destination_map.get(destination_id)
            if destination is None:
                raise Product2Page3VmError(f"destination_missing:{destination_id}")
            destination_group = destination_groups.get(destination_id)
            if destination_group is None:
                destination_group = {
                    "destination_id": destination.destination_id,
                    "display_name": destination.display_name,
                    "rows": {},
                    "order": destination_order.get(destination_id, 0),
                }
                destination_groups[destination_id] = destination_group
            rows_map: dict[str, dict[str, object]] = destination_group["rows"]  # type: ignore[assignment]
            for combination_key, quantity in breakdown.per_combination.items():
                if int(quantity) <= 0:
                    continue
                label = _combo_label_from_key(combination_key, requirement_name_map)
                row = rows_map.get(combination_key)
                if row is None:
                    row = {
                        "combination_key": combination_key,
                        "label": label,
                        "quantity": 0,
                        "dishes": {},
                    }
                    rows_map[combination_key] = row
                row["quantity"] = int(row["quantity"]) + int(quantity)
                dishes: dict[str, dict[str, object]] = row["dishes"]  # type: ignore[assignment]
                dish = dishes.get(option_result.option_id)
                if dish is None:
                    dish = {
                        "option_id": option_result.option_id,
                        "display_title": option_result.display_title,
                        "quantity": 0,
                        "order": option_order.get(option_result.option_id, 0),
                    }
                    dishes[option_result.option_id] = dish
                dish["quantity"] = int(dish["quantity"]) + int(quantity)

    groups: list[Product2Page3SpecialDestinationGroupVM] = []
    for destination_id, destination_group in sorted(
        destination_groups.items(),
        key=lambda item: (int(item[1].get("order", 0)), str(item[1].get("display_name", ""))),
    ):
        rows_map: dict[str, dict[str, object]] = destination_group["rows"]  # type: ignore[assignment]
        if not rows_map:
            continue
        rows: list[Product2Page3SpecialDestinationRowVM] = []
        for row in sorted(rows_map.values(), key=lambda item: (-(int(item.get("quantity", 0))), str(item.get("label", "")))):
            dishes_map: dict[str, dict[str, object]] = row["dishes"]  # type: ignore[assignment]
            dishes: list[Product2Page3SpecialDestinationDishVM] = []
            for dish in sorted(dishes_map.values(), key=lambda item: (int(item.get("order", 0)), str(item.get("display_title", "")))):
                dishes.append(
                    Product2Page3SpecialDestinationDishVM(
                        option_id=str(dish.get("option_id", "")),
                        display_title=str(dish.get("display_title", "")),
                        quantity=int(dish.get("quantity", 0)),
                    )
                )
            rows.append(
                Product2Page3SpecialDestinationRowVM(
                    combination_key=str(row["combination_key"]),
                    label=str(row["label"]),
                    quantity=int(row["quantity"]),
                    dishes=tuple(dishes),
                )
            )
        groups.append(
            Product2Page3SpecialDestinationGroupVM(
                destination_id=str(destination_group["destination_id"]),
                display_name=str(destination_group["display_name"]),
                rows=tuple(rows),
            )
        )
    return tuple(groups)


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
    view: str | None = None,
    special_view: str | None = None,
) -> Product2Page3VM:
    normalized_tenant_id = _normalize_tenant_id(tenant_id)
    normalized_site_id = _normalize_site_id(site_id)
    normalized_service_date = _normalize_service_date(service_date)
    normalized_meal = _normalize_meal(meal)
    normalized_view = str(view or "overview").strip().lower()
    if normalized_view not in {"overview", "normal", "special"}:
        normalized_view = "overview"
    normalized_special_view = str(special_view or "production").strip().lower()
    if normalized_special_view not in {"production", "department"}:
        normalized_special_view = "production"

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

    overview_options = tuple(options)
    normal_matrix = _build_normal_matrix(
        options=meal_result.options,
        context_options=page2_context.options,
        destination_map=destination_map,
    )
    special_production_groups = _build_special_production_groups(
        options=meal_result.options,
        context_options=page2_context.options,
        destination_map=destination_map,
        requirement_name_map=requirement_name_map,
    )
    special_destination_groups = _build_special_destination_groups(
        options=meal_result.options,
        context_options=page2_context.options,
        destination_map=destination_map,
        requirement_name_map=requirement_name_map,
    )

    base_url = (
        f"/ui/kitchen/planering/day/production?ui=product2&site_id={normalized_site_id}"
        f"&date={normalized_service_date.isoformat()}&meal={normalized_meal}"
    )
    navigation_urls = {
        "overview": f"{base_url}&view=overview",
        "normal": f"{base_url}&view=normal",
        "special": f"{base_url}&view=special&special_view={normalized_special_view}",
    }
    special_navigation_urls = {
        "production": f"{base_url}&view=special&special_view=production",
        "department": f"{base_url}&view=special&special_view=department",
    }

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
        service_date_compact_label=_format_service_date_compact_label(normalized_service_date),
        meal=normalized_meal,
        meal_label="Lunch" if normalized_meal == "lunch" else normalized_meal.capitalize(),
        ready=bool(meal_result.ready),
        ready_label="Underlag granskat" if meal_result.ready else "Underlag behöver granskas",
        blockers=meal_result.blockers,
        blocker_messages=tuple(blocker_messages),
        view=normalized_view,
        special_view=normalized_special_view,
        overview_options=overview_options,
        normal_matrix=normal_matrix,
        special_production_groups=special_production_groups,
        special_destination_groups=special_destination_groups,
        page2_url=f"/ui/kitchen/planering/day?ui=product2&site_id={normalized_site_id}&date={normalized_service_date.isoformat()}&meal={normalized_meal}",
        navigation_urls=navigation_urls,
        special_navigation_urls=special_navigation_urls,
        publication_identity=meal_result.publication_identity,
        options=tuple(options),
        unassigned_destinations=tuple(unassigned_destinations),
    )


__all__ = [
    "Product2Page3DepartmentQuantityVM",
    "Product2Page3NormalMatrixCellVM",
    "Product2Page3NormalMatrixColumnVM",
    "Product2Page3NormalMatrixRowVM",
    "Product2Page3NormalMatrixVM",
    "Product2Page3OptionVM",
    "Product2Page3DestinationVM",
    "Product2Page3SpecialDestinationDishVM",
    "Product2Page3SpecialDestinationGroupVM",
    "Product2Page3SpecialDestinationRowVM",
    "Product2Page3SpecialDishVM",
    "Product2Page3SpecialProductionGroupVM",
    "Product2Page3SpecialCohortVM",
    "Product2Page3VM",
    "Product2Page3VmError",
    "build_product2_page3_vm",
]