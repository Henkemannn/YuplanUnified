from __future__ import annotations

from .alias_domain import CompositionAlias


class InMemoryCompositionAliasRepository:
    def __init__(self) -> None:
        self._aliases: dict[str, CompositionAlias] = {}

    def add(self, alias: CompositionAlias) -> None:
        if alias.alias_id in self._aliases:
            raise ValueError(f"alias already exists: {alias.alias_id}")
        self._aliases[alias.alias_id] = alias

    def list_all(self) -> list[CompositionAlias]:
        return list(self._aliases.values())

    def find_by_alias_norm(self, alias_norm: str) -> list[CompositionAlias]:
        return [alias for alias in self._aliases.values() if alias.alias_norm == alias_norm]

    def list_for_composition(self, composition_id: str) -> list[CompositionAlias]:
        return [alias for alias in self._aliases.values() if alias.composition_id == composition_id]
