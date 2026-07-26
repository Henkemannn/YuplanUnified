from __future__ import annotations

from dataclasses import dataclass

from flask import has_app_context, url_for

from .planera_v2.contracts import PlanningComponentReference, PlanningCompositionReference


def _safe_builder_url(endpoint: str, **values: object) -> str:
    if has_app_context():
        try:
            return url_for(endpoint, **values)
        except Exception:
            pass

    composition_id = str(values.get("composition_id") or "").strip()
    component_id = str(values.get("component_id") or "").strip()
    if endpoint == "ui.builder_internal_ui":
        if composition_id:
            return f"/builder?composition_id={composition_id}"
        if component_id:
            return f"/builder?component_id={component_id}"
        return "/builder"
    if endpoint == "builder_api.render_composition_text" and composition_id:
        return f"/builder?composition_id={composition_id}"
    if endpoint == "builder_api.get_composition_declaration_readiness" and composition_id:
        return f"/builder?composition_id={composition_id}"
    if endpoint == "builder_api.get_component_details" and component_id:
        return f"/builder?component_id={component_id}"
    if endpoint == "builder_api.list_component_recipes" and component_id:
        return f"/builder?component_id={component_id}"
    return ""


@dataclass(frozen=True, slots=True)
class OffshoreBuilderBridgeService:
    def build_composition_bridge(
        self,
        *,
        tenant_id: int | None,
        composition_reference: PlanningCompositionReference | None,
        component_references: tuple[PlanningComponentReference, ...] = (),
    ) -> dict[str, object] | None:
        if tenant_id is None or composition_reference is None:
            return None

        composition_id = str(composition_reference.composition_id or "").strip()
        if not composition_id:
            return None

        components = [
            {
                "component_id": reference.component_id,
                "component_name": reference.component_name,
                "role": reference.role,
                "sort_order": reference.sort_order,
                "details_url": _safe_builder_url("ui.builder_internal_ui", component_id=reference.component_id),
                "recipes_url": _safe_builder_url("ui.builder_internal_ui", component_id=reference.component_id),
            }
            for reference in component_references
            if str(reference.component_id or "").strip()
        ]

        return {
            "tenant_id": tenant_id,
            "composition_id": composition_id,
            "composition_name": str(composition_reference.composition_name or composition_id).strip(),
            "component_count": len(components),
            "builder_url": _safe_builder_url("ui.builder_internal_ui", composition_id=composition_id),
            "render_url": _safe_builder_url("builder_api.render_composition_text", composition_id=composition_id),
            "readiness_url": _safe_builder_url("builder_api.get_composition_declaration_readiness", composition_id=composition_id),
            "components": components,
        }


_service = OffshoreBuilderBridgeService()