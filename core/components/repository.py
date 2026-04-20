from __future__ import annotations

from .domain import Component


class InMemoryComponentRepository:
    def __init__(self) -> None:
        self._components: dict[str, Component] = {}

    def add(self, component: Component) -> None:
        if component.component_id in self._components:
            raise ValueError(f"component already exists: {component.component_id}")
        self._components[component.component_id] = component

    def get(self, component_id: str) -> Component | None:
        return self._components.get(component_id)

    def update(self, component: Component) -> None:
        if component.component_id not in self._components:
            raise ValueError(f"component not found: {component.component_id}")
        self._components[component.component_id] = component

    def list_all(self) -> list[Component]:
        return list(self._components.values())

    def list_active(self) -> list[Component]:
        return [component for component in self._components.values() if component.is_active]
