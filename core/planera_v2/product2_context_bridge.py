from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..planera_product2_page2_context import Product2Page2ContextError as _Product2Page2ContextError


Product2Page2ContextError = _Product2Page2ContextError


@runtime_checkable
class Product2Page2PublicationIdentityLike(Protocol):
    builder_menu_id: str
    builder_menu_version: int


@runtime_checkable
class Product2Page2RequirementLike(Protocol):
    dietary_type_id: int
    requirement_key: str | None
    name: str
    semantics: str | None


@runtime_checkable
class Product2Page2RequirementGroupLike(Protocol):
    requirement_group_id: str
    destination_id: str
    label: str | None
    effective_quantity: int
    requirements: tuple[Product2Page2RequirementLike, ...]


@runtime_checkable
class Product2Page2DestinationLike(Protocol):
    destination_id: str
    display_name: str
    baseline_quantity: int
    selected_option_id: str | None
    choice_source: str


@runtime_checkable
class Product2MealOptionLike(Protocol):
    option_id: str
    display_title: str
    variant_type: str
    display_label: str | None


@runtime_checkable
class Product2Page2PlanningContextLike(Protocol):
    site_id: str
    service_date: str
    meal: str
    status: str
    publication_identity: Product2Page2PublicationIdentityLike | None
    options: tuple[Product2MealOptionLike, ...]
    destinations: tuple[Product2Page2DestinationLike, ...]
    requirement_groups: tuple[Product2Page2RequirementGroupLike, ...]
    target_option_id: str | None
    target_display_label: str | None
    target_display_title: str | None
    has_target_demand: bool
    unresolved_destination_count: int


def build_product2_page2_planning_context(*, tenant_id, site_id, service_date, meal):
    from ..planera_product2_page2_context import build_product2_page2_planning_context as _build

    return _build(tenant_id=tenant_id, site_id=site_id, service_date=service_date, meal=meal)


def build_product2_page2_target_planning_context(*, tenant_id, site_id, service_date, meal, option_id):
    from ..planera_product2_page2_context import build_product2_page2_target_planning_context as _build

    return _build(tenant_id=tenant_id, site_id=site_id, service_date=service_date, meal=meal, option_id=option_id)
