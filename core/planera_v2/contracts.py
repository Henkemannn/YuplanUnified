from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EffectiveMenuSourceType(str, Enum):
    PUBLISHED_BUILDER_ITEM = "published_builder_item"
    OPERATIONAL_BUILDER_OVERRIDE = "operational_builder_override"
    OPERATIONAL_FREE_TEXT = "operational_free_text"


class EffectiveMenuReadiness(str, Enum):
    STRUCTURED = "structured"
    PARTIALLY_STRUCTURED = "partially_structured"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class PlanningTrackDefinition:
    track_key: str
    track_label: str
    track_group: str

    @property
    def key(self) -> str:
        return self.track_key

    @property
    def label(self) -> str:
        return self.track_label

    @property
    def group(self) -> str:
        return self.track_group


@dataclass(frozen=True, slots=True)
class PlanningCompositionOption:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class PlanningWorkPeriodReference:
    id: int
    name: str
    status: str
    starts_at: str
    ends_at: str


@dataclass(frozen=True, slots=True)
class PlanningPublicationReference:
    publication_pin_id: str | None
    builder_menu_id: str | None
    builder_menu_version: int | None
    publication_year: int | None
    publication_week: int | None


@dataclass(frozen=True, slots=True)
class PlanningOperationalDecisionReference:
    decision_id: int | None
    decision_type: str
    source_publication_pin_id: str | None
    source_publication_year: int | None
    source_publication_week: int | None
    builder_composition_id: str | None
    free_text: str | None


@dataclass(frozen=True, slots=True)
class PlanningCompositionReference:
    composition_id: str
    composition_name: str


@dataclass(frozen=True, slots=True)
class PlanningComponentReference:
    component_id: str
    component_name: str
    role: str | None = None
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class EffectivePlanningMenuItem:
    stable_item_id: str
    tenant_id: int
    installation_id: str
    service_event_id: int
    service_date: str
    meal_slot: str
    service_label: str
    track_key: str
    track_label: str
    track_group: str
    source_type: EffectiveMenuSourceType
    readiness: EffectiveMenuReadiness
    display_name: str | None
    published_title: str | None
    effective_title: str | None
    published_reference: PlanningPublicationReference | None = None
    operational_decision_reference: PlanningOperationalDecisionReference | None = None
    builder_composition_reference: PlanningCompositionReference | None = None
    component_references: tuple[PlanningComponentReference, ...] = ()
    capabilities: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    decision_type: str | None = None
    decision_label: str | None = None
    row_state: str = "published"


@dataclass(frozen=True, slots=True)
class PlanningServiceEvent:
    service_event_id: int
    service_date: str
    meal_slot: str
    service_label: str
    sequence_order: int
    local_time: str
    menu_context_status: str
    menu_title: str | None
    items: tuple[EffectivePlanningMenuItem, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanningMenuContext:
    adapter_version: str
    tenant_id: int | None
    organization_id: int | None
    tenant_name: str | None
    installation_id: str | None
    installation_name: str | None
    work_period: PlanningWorkPeriodReference | None
    period_start: str | None
    period_end: str | None
    generated_at: datetime
    track_groups: tuple[tuple[str, tuple[PlanningTrackDefinition, ...]], ...] = ()
    composition_options: tuple[PlanningCompositionOption, ...] = ()
    service_events: tuple[PlanningServiceEvent, ...] = ()
    warnings: tuple[str, ...] = ()


def build_capabilities(*, has_builder_composition: bool, has_components: bool, readiness: EffectiveMenuReadiness) -> tuple[str, ...]:
    capabilities: list[str] = []
    if has_builder_composition:
        capabilities.append("has_builder_composition")
    if has_components:
        capabilities.extend(
            [
                "has_components",
                "can_resolve_recipe_data",
                "can_resolve_allergens",
                "can_resolve_prep",
            ]
        )
    if readiness == EffectiveMenuReadiness.STRUCTURED:
        capabilities.append("production_structure_ready")
    return tuple(capabilities)


__all__ = [
    "EffectiveMenuReadiness",
    "EffectiveMenuSourceType",
    "EffectivePlanningMenuItem",
    "PlanningComponentReference",
    "PlanningCompositionOption",
    "PlanningCompositionReference",
    "PlanningMenuContext",
    "PlanningOperationalDecisionReference",
    "PlanningPublicationReference",
    "PlanningServiceEvent",
    "PlanningTrackDefinition",
    "PlanningWorkPeriodReference",
    "build_capabilities",
]