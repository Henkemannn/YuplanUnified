from __future__ import annotations

from .composition_domain import Composition, CompositionComponent
from .composition_repository import InMemoryCompositionRepository


class CompositionService:
    def __init__(self, repository: InMemoryCompositionRepository | None = None) -> None:
        self._repository = repository or InMemoryCompositionRepository()

    def create_composition(
        self,
        composition_id: str,
        composition_name: str,
        *,
        library_group: str | None = None,
        components: list[CompositionComponent] | None = None,
    ) -> Composition:
        composition_id_value = str(composition_id or "").strip()
        if not composition_id_value:
            raise ValueError("composition_id must be non-empty")

        composition_name_value = str(composition_name or "").strip()
        if not composition_name_value:
            raise ValueError("composition_name must be non-empty")

        composition = Composition(
            composition_id=composition_id_value,
            composition_name=composition_name_value,
            library_group=str(library_group).strip() if library_group is not None else None,
            components=sorted(list(components or []), key=lambda item: item.sort_order),
        )
        self._repository.add(composition)
        return composition

    def get_composition(self, composition_id: str) -> Composition | None:
        return self._repository.get(composition_id)

    def list_compositions(self, *, group_name: str | None = None) -> list[Composition]:
        if group_name is None:
            return self._repository.list_all()
        return self._repository.list_by_group(group_name)

    def add_component_to_composition(
        self,
        composition_id: str,
        component_id: str,
        *,
        component_name: str | None = None,
        role: str | None = None,
        sort_order: int | None = None,
    ) -> Composition:
        composition = self._require_composition(composition_id)

        component_id_value = str(component_id or "").strip()
        if not component_id_value:
            raise ValueError("component_id must be non-empty")

        component_name_value = str(
            component_name if component_name is not None else component_id_value
        ).strip()
        if not component_name_value:
            component_name_value = component_id_value

        resolved_sort_order = self._resolve_sort_order(composition, sort_order)
        for existing in composition.components:
            if existing.component_id == component_id_value and existing.sort_order == resolved_sort_order:
                raise ValueError(
                    "duplicate component entry for same component_id and sort_order"
                )

        updated_components = list(composition.components)
        updated_components.append(
            CompositionComponent(
                component_id=component_id_value,
                component_name=component_name_value,
                role=str(role).strip() if role is not None else None,
                sort_order=resolved_sort_order,
            )
        )
        updated_components.sort(key=lambda item: item.sort_order)

        updated = Composition(
            composition_id=composition.composition_id,
            composition_name=composition.composition_name,
            library_group=composition.library_group,
            components=updated_components,
        )
        self._repository.update(updated)
        return updated

    def remove_component_from_composition(
        self,
        composition_id: str,
        component_id: str,
        *,
        sort_order: int | None = None,
    ) -> Composition:
        composition = self._require_composition(composition_id)
        component_id_value = str(component_id or "").strip()
        if not component_id_value:
            raise ValueError("component_id must be non-empty")

        updated_components: list[CompositionComponent] = []
        removed = False
        for existing in composition.components:
            if removed:
                updated_components.append(existing)
                continue

            matches_component = existing.component_id == component_id_value
            matches_sort_order = sort_order is None or existing.sort_order == int(sort_order)

            if matches_component and matches_sort_order:
                removed = True
                continue

            updated_components.append(existing)

        if not removed:
            raise ValueError("component entry not found in composition")

        updated = Composition(
            composition_id=composition.composition_id,
            composition_name=composition.composition_name,
            library_group=composition.library_group,
            components=updated_components,
        )
        self._repository.update(updated)
        return updated

    def _require_composition(self, composition_id: str) -> Composition:
        composition_id_value = str(composition_id or "").strip()
        if not composition_id_value:
            raise ValueError("composition_id must be non-empty")

        composition = self._repository.get(composition_id_value)
        if composition is None:
            raise ValueError(f"composition not found: {composition_id_value}")
        return composition

    @staticmethod
    def _resolve_sort_order(composition: Composition, sort_order: int | None) -> int:
        if sort_order is not None:
            return int(sort_order)
        if not composition.components:
            return 10
        return max(item.sort_order for item in composition.components) + 10
