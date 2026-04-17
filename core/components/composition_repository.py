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
