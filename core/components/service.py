from __future__ import annotations

from .domain import Component
from .repository import InMemoryComponentRepository


class ComponentService:
    def __init__(self, repository: InMemoryComponentRepository | None = None) -> None:
        self._repository = repository or InMemoryComponentRepository()

    def create_component(
        self,
        component_id: str,
        canonical_name: str,
        is_active: bool = True,
        default_uom: str | None = None,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> Component:
        component = Component(
            component_id=component_id,
            canonical_name=canonical_name,
            is_active=is_active,
            default_uom=default_uom,
            tags=list(tags) if tags is not None else [],
            categories=list(categories) if categories is not None else [],
            primary_recipe_id=None,
        )
        self._repository.add(component)
        return component

    def get_component(self, component_id: str) -> Component | None:
        return self._repository.get(component_id)

    def list_components(self, active_only: bool = False) -> list[Component]:
        if active_only:
            return self._repository.list_active()
        return self._repository.list_all()

    def delete_component(self, component_id: str) -> None:
        component_id_value = str(component_id or "").strip()
        if not component_id_value:
            raise ValueError("component_id must be non-empty")
        self._repository.delete(component_id_value)

    def set_primary_recipe_id(
        self,
        component_id: str,
        recipe_id: str | None,
    ) -> Component:
        component_id_value = str(component_id or "").strip()
        if not component_id_value:
            raise ValueError("component_id must be non-empty")

        component = self._repository.get(component_id_value)
        if component is None:
            raise ValueError(f"component not found: {component_id_value}")

        recipe_id_value = str(recipe_id or "").strip() or None
        updated = Component(
            component_id=component.component_id,
            canonical_name=component.canonical_name,
            is_active=component.is_active,
            default_uom=component.default_uom,
            tags=list(component.tags),
            categories=list(component.categories),
            primary_recipe_id=recipe_id_value,
        )
        self._repository.update(updated)
        return updated

    def set_component_category(self, component_id: str, category: str | None) -> Component:
        component_id_value = str(component_id or "").strip()
        if not component_id_value:
            raise ValueError("component_id must be non-empty")

        component = self._repository.get(component_id_value)
        if component is None:
            raise ValueError(f"component not found: {component_id_value}")

        category_value = str(category or "").strip().lower()
        categories = [category_value] if category_value else []
        updated = Component(
            component_id=component.component_id,
            canonical_name=component.canonical_name,
            is_active=component.is_active,
            default_uom=component.default_uom,
            tags=list(component.tags),
            categories=categories,
            primary_recipe_id=component.primary_recipe_id,
        )
        self._repository.update(updated)
        return updated

    def rename_component(self, component_id: str, canonical_name: str) -> Component:
        component_id_value = str(component_id or "").strip()
        if not component_id_value:
            raise ValueError("component_id must be non-empty")

        name_value = str(canonical_name or "").strip()
        if not name_value:
            raise ValueError("component_name must be non-empty")

        component = self._repository.get(component_id_value)
        if component is None:
            raise ValueError(f"component not found: {component_id_value}")

        updated = Component(
            component_id=component.component_id,
            canonical_name=name_value,
            is_active=component.is_active,
            default_uom=component.default_uom,
            tags=list(component.tags),
            categories=list(component.categories),
            primary_recipe_id=component.primary_recipe_id,
        )
        self._repository.update(updated)
        return updated
