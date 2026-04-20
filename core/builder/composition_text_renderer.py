from __future__ import annotations

from dataclasses import dataclass, field

from ..components import Composition


@dataclass(frozen=True)
class RenderedCompositionComponent:
    component_id: str
    component_name: str
    role: str | None
    sort_order: int
    text_token: str


@dataclass(frozen=True)
class RenderedCompositionTextModel:
    composition_id: str
    composition_name: str
    rendered_components: list[RenderedCompositionComponent] = field(default_factory=list)
    text: str = ""


def render_composition_to_text_model(composition: Composition) -> RenderedCompositionTextModel:
    ordered_components = sorted(
        list(composition.components),
        key=lambda item: (
            int(item.sort_order),
            str(item.component_name or item.component_id or "").lower(),
            str(item.component_id or ""),
        ),
    )

    rendered_components: list[RenderedCompositionComponent] = []
    for item in ordered_components:
        name_value = str(item.component_name or item.component_id or "").strip()
        role_value = str(item.role or "").strip() or None
        text_token = name_value if role_value is None else f"{name_value} ({role_value})"
        rendered_components.append(
            RenderedCompositionComponent(
                component_id=str(item.component_id or ""),
                component_name=name_value,
                role=role_value,
                sort_order=int(item.sort_order),
                text_token=text_token,
            )
        )

    tokens = [item.text_token for item in rendered_components]
    if tokens:
        text = str(composition.composition_name) + ": " + ", ".join(tokens)
    else:
        text = str(composition.composition_name)

    return RenderedCompositionTextModel(
        composition_id=str(composition.composition_id),
        composition_name=str(composition.composition_name),
        rendered_components=rendered_components,
        text=text,
    )
