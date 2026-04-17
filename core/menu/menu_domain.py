from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuDetail:
    menu_detail_id: str
    menu_id: str
    day: str
    meal_slot: str
    composition_ref_type: str
    composition_id: str | None = None
    unresolved_text: str | None = None
    note: str | None = None
    sort_order: int = 0
