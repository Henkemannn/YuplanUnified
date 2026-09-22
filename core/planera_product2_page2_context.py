from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from .commun_builder_publication import CommunBuilderPublicationService
from .commun_builder_projection import get_shadow_projection_reader
from .department_requirement_group_repo import DepartmentRequirementGroupsRepo
from .department_requirement_group_service_overrides_repo import (
    DepartmentRequirementGroupServiceOverridesRepo,
)
from .db import get_site_tenant
from .planera_product2_menu_vm import (
    Product2MealOptionVM,
    Product2MealOptionsError,
    build_product2_meal_options_vm,
)
from .planera_v2.day_context_resolver import resolve_kommun_day_business_context
from .department_menu_choice_repo import MenuChoiceRepo


class Product2Page2ContextError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Product2Page2PublicationIdentity:
    builder_menu_id: str
    builder_menu_version: int


@dataclass(frozen=True, slots=True)
class Product2Page2RequirementVM:
    dietary_type_id: int
    requirement_key: str | None
    name: str
    semantics: str | None


@dataclass(frozen=True, slots=True)
class Product2Page2RequirementGroupVM:
    requirement_group_id: str
    destination_id: str
    label: str | None
    effective_quantity: int
    requirements: tuple[Product2Page2RequirementVM, ...]


@dataclass(frozen=True, slots=True)
class Product2Page2DestinationVM:
    destination_id: str
    display_name: str
    baseline_quantity: int
    selected_option_id: str | None
    choice_source: str


@dataclass(frozen=True, slots=True)
class Product2Page2PlanningContext:
    site_id: str
    service_date: str
    meal: str
    status: str
    publication_identity: Product2Page2PublicationIdentity | None
    options: tuple[Product2MealOptionVM, ...]
    destinations: tuple[Product2Page2DestinationVM, ...]
    requirement_groups: tuple[Product2Page2RequirementGroupVM, ...]


_MEAL_DAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _normalize_tenant_id(value: object) -> int:
    try:
        tenant_id = int(value)
    except Exception as exc:
        raise Product2Page2ContextError("tenant_id_missing") from exc
    if tenant_id <= 0:
        raise Product2Page2ContextError("tenant_id_missing")
    return tenant_id


def _normalize_site_id(value: object) -> str:
    site_id = str(value or "").strip()
    if not site_id:
        raise Product2Page2ContextError("site_id_missing")
    return site_id


def _normalize_service_date(value: object) -> _date:
    if isinstance(value, _date):
        return value
    raw = str(value or "").strip()
    if not raw:
        raise Product2Page2ContextError("service_date_missing")
    try:
        return _date.fromisoformat(raw)
    except Exception as exc:
        raise Product2Page2ContextError("service_date_invalid") from exc


def _normalize_meal(value: object) -> str:
    meal = str(value or "").strip().lower()
    if meal != "lunch":
        raise Product2Page2ContextError("meal_unsupported")
    return meal


def _day_name_for_service_date(service_date: _date) -> str:
    return _MEAL_DAY_NAMES[service_date.isocalendar()[2] - 1]


def _build_publication_identity(publication) -> Product2Page2PublicationIdentity:
    return Product2Page2PublicationIdentity(
        builder_menu_id=str(publication.builder_menu_id),
        builder_menu_version=int(publication.builder_menu_version),
    )


def _unique_option_for_variant(options: tuple[Product2MealOptionVM, ...], variant_type: str) -> Product2MealOptionVM | None:
    matches = [option for option in options if str(option.variant_type).strip().lower() == variant_type]
    if not matches:
        return None
    if len(matches) != 1:
        raise Product2Page2ContextError(f"ambiguous_option_variant:{variant_type}")
    return matches[0]


def _build_requirement_groups(
    *,
    tenant_id: int,
    service_date: _date,
    meal: str,
    destination_by_id: dict[str, Product2Page2DestinationVM],
) -> tuple[Product2Page2RequirementGroupVM, ...]:
    group_repo = DepartmentRequirementGroupsRepo()
    override_repo = DepartmentRequirementGroupServiceOverridesRepo()
    grouped: list[Product2Page2RequirementGroupVM] = []

    for destination_id in destination_by_id:
        for group in group_repo.list_for_department(destination_id):
            group_id = str(group.get("id") or "").strip()
            if not group_id:
                continue
            effective_quantity = int(
                override_repo.resolve_effective_quantity(group_id, service_date, meal)
            )
            if effective_quantity <= 0:
                continue
            requirements = tuple(
                Product2Page2RequirementVM(
                    dietary_type_id=int(requirement.get("dietary_type_id") or 0),
                    requirement_key=str(requirement.get("requirement_key") or "").strip() or None,
                    name=str(requirement.get("name") or ""),
                    semantics=str(requirement.get("semantics") or "").strip() or None,
                )
                for requirement in (group.get("requirements") or [])
                if int(requirement.get("dietary_type_id") or 0) > 0
            )
            grouped.append(
                Product2Page2RequirementGroupVM(
                    requirement_group_id=group_id,
                    destination_id=destination_id,
                    label=str(group.get("label") or "").strip() or None,
                    effective_quantity=effective_quantity,
                    requirements=requirements,
                )
            )

    return tuple(grouped)


def _choice_source_and_option_id(
    *,
    selected_variant: str | None,
    options: tuple[Product2MealOptionVM, ...],
) -> tuple[str, str | None]:
    if not selected_variant:
        return "none", None
    option = _unique_option_for_variant(options, selected_variant)
    if option is None:
        raise Product2Page2ContextError(f"selected_variant_missing_from_publication:{selected_variant}")
    return "explicit", option.option_id


def build_product2_page2_planning_context(
    *,
    tenant_id,
    site_id,
    service_date,
    meal,
) -> Product2Page2PlanningContext:
    normalized_tenant_id = _normalize_tenant_id(tenant_id)
    normalized_site_id = _normalize_site_id(site_id)
    normalized_service_date = _normalize_service_date(service_date)
    normalized_meal = _normalize_meal(meal)
    year, week, weekday = normalized_service_date.isocalendar()

    day_context = resolve_kommun_day_business_context(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        service_date=normalized_service_date,
        meal_labels={"lunch": "Lunch", "dinner": "Dinner"},
    )

    publication_service = CommunBuilderPublicationService()
    publication = publication_service.get_publication_for_week(
        tenant_id=normalized_tenant_id,
        site_id=normalized_site_id,
        year=year,
        week=week,
    )

    publication_identity = None
    options: tuple[Product2MealOptionVM, ...] = ()
    status = "no_publication"
    if publication is not None:
        publication_identity = _build_publication_identity(publication)
        outcome = get_shadow_projection_reader().get_projection_for_pinned_menu(
            tenant_id=normalized_tenant_id,
            site_id=normalized_site_id,
            year=year,
            week=week,
            builder_menu_id=publication_identity.builder_menu_id,
            builder_menu_version=publication_identity.builder_menu_version,
        )
        if outcome.status != "ok" or outcome.projection is None:
            raise Product2Page2ContextError(f"publication_projection_invalid:{outcome.error or outcome.status}")
        if any(bool(row.error) for row in outcome.projection.rows):
            raise Product2Page2ContextError("publication_projection_invalid:row_error")
        status = "ok"
        try:
            options_vm = build_product2_meal_options_vm(
                outcome.projection.rows,
                day=_day_name_for_service_date(normalized_service_date),
                meal=normalized_meal,
            )
        except Product2MealOptionsError as exc:
            raise Product2Page2ContextError(str(exc)) from exc
        options = options_vm.options

    destination_rows = []
    for department in day_context.departments:
        destination_id = str(department.department_id)
        display_name = str(department.department_name or department.department_id)
        baseline_quantity = int(day_context.lunch_baselines.get(destination_id, 0))
        selected_option_id = None
        choice_source = "none"
        if publication is not None:
            choice_repo = MenuChoiceRepo()
            rows = choice_repo.list_for_department_week(
                tenant_id=normalized_tenant_id,
                site_id=normalized_site_id,
                department_id=destination_id,
                year=year,
                week=week,
            )
            explicit_row = None
            for row in rows:
                if int(row.weekday) == int(weekday) and str(row.meal).strip().lower() == normalized_meal:
                    explicit_row = row
                    break
            if explicit_row is not None:
                choice_source, selected_option_id = _choice_source_and_option_id(
                    selected_variant=str(explicit_row.selected_variant).strip().lower(),
                    options=options,
                )
        destination_rows.append(
            Product2Page2DestinationVM(
                destination_id=destination_id,
                display_name=display_name,
                baseline_quantity=baseline_quantity,
                selected_option_id=selected_option_id,
                choice_source=choice_source,
            )
        )

    destinations = tuple(destination_rows)
    destination_by_id = {destination.destination_id: destination for destination in destinations}
    requirement_groups = _build_requirement_groups(
        tenant_id=normalized_tenant_id,
        service_date=normalized_service_date,
        meal=normalized_meal,
        destination_by_id=destination_by_id,
    )

    return Product2Page2PlanningContext(
        site_id=normalized_site_id,
        service_date=normalized_service_date.isoformat(),
        meal=normalized_meal,
        status=status,
        publication_identity=publication_identity,
        options=options,
        destinations=destinations,
        requirement_groups=requirement_groups,
    )


__all__ = [
    "Product2Page2ContextError",
    "Product2Page2DestinationVM",
    "Product2Page2PlanningContext",
    "Product2Page2PublicationIdentity",
    "Product2Page2RequirementGroupVM",
    "Product2Page2RequirementVM",
    "build_product2_page2_planning_context",
]