from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ComponentAlias:
    alias_id: str
    component_id: str
    alias_text: str
    alias_norm: str
    source: str
    confidence: Decimal | float | None = None
