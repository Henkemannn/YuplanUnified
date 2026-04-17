from __future__ import annotations

from .composition_domain import Composition


class InMemoryCompositionRepository:
    def __init__(self) -> None:
        self._compositions: dict[str, Composition] = {}

    def add(self, composition: Composition) -> None:
        if composition.composition_id in self._compositions:
            raise ValueError(f"composition already exists: {composition.composition_id}")
        self._compositions[composition.composition_id] = composition

    def get(self, composition_id: str) -> Composition | None:
        return self._compositions.get(composition_id)

    def list_all(self) -> list[Composition]:
        return list(self._compositions.values())

    def list_by_group(self, group_name: str) -> list[Composition]:
        return [
            composition
            for composition in self._compositions.values()
            if composition.library_group == group_name
        ]

    def update(self, composition: Composition) -> None:
        if composition.composition_id not in self._compositions:
            raise ValueError(f"composition not found: {composition.composition_id}")
        self._compositions[composition.composition_id] = composition
