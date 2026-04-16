from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Component:
    component_id: str
    canonical_name: str
    is_active: bool = True
    default_uom: str | None = None
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
