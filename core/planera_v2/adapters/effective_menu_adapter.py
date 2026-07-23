from __future__ import annotations

from typing import Any

from ..contracts import (
    EffectivePlanningMenuItem,
    PlanningMenuContext,
    PlanningServiceEvent,
)


_ADAPTER_VERSION = "effective-menu-adapter/v1"


def _serialize_item(item: EffectivePlanningMenuItem) -> dict[str, Any]:
    return {
        "stable_item_id": item.stable_item_id,
        "tenant_id": item.tenant_id,
        "installation_id": item.installation_id,
        "service_event_id": item.service_event_id,
        "service_date": item.service_date,
        "meal_slot": item.meal_slot,
        "service_label": item.service_label,
        "track_key": item.track_key,
        "track_label": item.track_label,
        "track_group": item.track_group,
        "source_type": item.source_type.value,
        "readiness": item.readiness.value,
        "display_name": item.display_name,
        "published_title": item.published_title,
        "effective_title": item.effective_title,
        "published_reference": None
        if item.published_reference is None
        else {
            "publication_pin_id": item.published_reference.publication_pin_id,
            "builder_menu_id": item.published_reference.builder_menu_id,
            "builder_menu_version": item.published_reference.builder_menu_version,
            "publication_year": item.published_reference.publication_year,
            "publication_week": item.published_reference.publication_week,
        },
        "operational_decision_reference": None
        if item.operational_decision_reference is None
        else {
            "decision_id": item.operational_decision_reference.decision_id,
            "decision_type": item.operational_decision_reference.decision_type,
            "source_publication_pin_id": item.operational_decision_reference.source_publication_pin_id,
            "source_publication_year": item.operational_decision_reference.source_publication_year,
            "source_publication_week": item.operational_decision_reference.source_publication_week,
            "builder_composition_id": item.operational_decision_reference.builder_composition_id,
            "free_text": item.operational_decision_reference.free_text,
        },
        "builder_composition_reference": None
        if item.builder_composition_reference is None
        else {
            "composition_id": item.builder_composition_reference.composition_id,
            "composition_name": item.builder_composition_reference.composition_name,
        },
        "component_references": [
            {
                "component_id": component.component_id,
                "component_name": component.component_name,
                "role": component.role,
                "sort_order": component.sort_order,
            }
            for component in item.component_references
        ],
        "capabilities": list(item.capabilities),
        "warnings": list(item.warnings),
        "decision_type": item.decision_type,
        "decision_label": item.decision_label,
        "row_state": item.row_state,
    }


def _serialize_event(event: PlanningServiceEvent) -> dict[str, Any]:
    return {
        "service_event_id": event.service_event_id,
        "service_date": event.service_date,
        "meal_slot": event.meal_slot,
        "service_label": event.service_label,
        "sequence_order": event.sequence_order,
        "local_time": event.local_time,
        "menu_context_status": event.menu_context_status,
        "menu_title": event.menu_title,
        "items": [_serialize_item(item) for item in event.items],
    }


def build_effective_planning_menu_payload(context: PlanningMenuContext) -> dict[str, Any]:
    return {
        "adapter_version": _ADAPTER_VERSION,
        "tenant_id": context.tenant_id,
        "organization_id": context.organization_id,
        "tenant_name": context.tenant_name,
        "installation_id": context.installation_id,
        "installation_name": context.installation_name,
        "work_period": None
        if context.work_period is None
        else {
            "id": context.work_period.id,
            "name": context.work_period.name,
            "status": context.work_period.status,
            "starts_at": context.work_period.starts_at,
            "ends_at": context.work_period.ends_at,
        },
        "period_start": context.period_start,
        "period_end": context.period_end,
        "generated_at": context.generated_at.isoformat(),
        "track_groups": [
            {
                "track_group": group_key,
                "tracks": [
                    {
                        "track_key": track.track_key,
                        "track_label": track.track_label,
                        "track_group": track.track_group,
                    }
                    for track in tracks
                ],
            }
            for group_key, tracks in context.track_groups
        ],
        "composition_options": [
            {"value": option.value, "label": option.label} for option in context.composition_options
        ],
        "service_events": [_serialize_event(event) for event in context.service_events],
        "warnings": list(context.warnings),
    }


def build_planera_input_from_effective_menu_context(context: PlanningMenuContext) -> dict[str, Any]:
    return {
        "baseline": 0,
        "units": [],
        "deviations": [],
        "context": build_effective_planning_menu_payload(context),
    }


__all__ = [
    "build_effective_planning_menu_payload",
    "build_planera_input_from_effective_menu_context",
]