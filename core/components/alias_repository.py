from __future__ import annotations

from .alias_domain import ComponentAlias


class InMemoryComponentAliasRepository:
    def __init__(self) -> None:
        self._aliases: dict[str, ComponentAlias] = {}

    def add(self, alias: ComponentAlias) -> None:
        if alias.alias_id in self._aliases:
            raise ValueError(f"alias already exists: {alias.alias_id}")
        self._aliases[alias.alias_id] = alias

    def list_all(self) -> list[ComponentAlias]:
        return list(self._aliases.values())

    def find_by_alias_norm(self, alias_norm: str) -> list[ComponentAlias]:
        return [alias for alias in self._aliases.values() if alias.alias_norm == alias_norm]

    def list_for_component(self, component_id: str) -> list[ComponentAlias]:
        component_id_value = str(component_id or "").strip()
        return [
            alias
            for alias in self._aliases.values()
            if alias.component_id == component_id_value
        ]
