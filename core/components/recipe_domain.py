from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    component_id: str
    recipe_name: str
    visibility: str
    is_default: bool = False
    yield_portions: int = 1
    notes: str | None = None


@dataclass(frozen=True)
class RecipeIngredientLine:
    recipe_ingredient_line_id: str
    recipe_id: str
    ingredient_name: str
    quantity_value: Decimal
    quantity_unit: str
    unit_price_value: Decimal | None = None
    unit_price_unit: str | None = None
    note: str | None = None
    sort_order: int = 0
