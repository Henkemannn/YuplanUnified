from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompositionComponent:
    component_id: str
    component_name: str | None = None
    role: str | None = None
    sort_order: int = 0


@dataclass(frozen=True)
class Composition:
    composition_id: str
    composition_name: str
    library_group: str | None = None
    components: list[CompositionComponent] = field(default_factory=list)
    use_custom_menu_name: bool = False
    menu_name: str | None = None

    @property
    def effective_menu_name(self) -> str:
        custom_name = str(self.menu_name or "").strip()
        if self.use_custom_menu_name and custom_name:
            return custom_name
        return self.composition_name
