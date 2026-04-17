from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CompositionAlias:
    alias_id: str
    composition_id: str
    alias_text: str
    alias_norm: str
    source: str
    confidence: Decimal | float | None = None
