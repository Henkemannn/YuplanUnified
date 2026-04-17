from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .recipe_domain import Recipe, RecipeIngredientLine


@dataclass(frozen=True)
class ScaledIngredientLine:
    ingredient_name: str
    original_quantity_value: Decimal
    quantity_unit: str
    scaled_quantity_value: Decimal
    unit_price_value: Decimal | None = None
    unit_price_unit: str | None = None
    line_cost: Decimal | None = None
    note: str | None = None
    sort_order: int = 0


@dataclass(frozen=True)
class RecipeCostBreakdown:
    recipe_id: str
    target_portions: int
    source_yield_portions: int
    scaled_lines: list[ScaledIngredientLine] = field(default_factory=list)
    total_cost: Decimal | None = None
    cost_per_portion: Decimal | None = None
    warnings: list[str] = field(default_factory=list)


def calculate_recipe_cost_breakdown(
    recipe: Recipe,
    ingredient_lines: list[RecipeIngredientLine],
    target_portions: int,
) -> RecipeCostBreakdown:
    if int(target_portions) <= 0:
        raise ValueError("target_portions must be > 0")

    source_yield_portions = int(recipe.yield_portions)
    if source_yield_portions <= 0:
        raise ValueError("recipe.yield_portions must be > 0")

    scaling_factor = Decimal(target_portions) / Decimal(source_yield_portions)

    scaled_lines: list[ScaledIngredientLine] = []
    partial_total_cost = Decimal("0")
    missing_price = False

    for line in ingredient_lines:
        scaled_quantity = line.quantity_value * scaling_factor
        line_cost: Decimal | None = None
        if line.unit_price_value is not None:
            # In v1 we assume unit_price_unit matches quantity_unit.
            line_cost = scaled_quantity * line.unit_price_value
            partial_total_cost += line_cost
        else:
            missing_price = True

        scaled_lines.append(
            ScaledIngredientLine(
                ingredient_name=line.ingredient_name,
                original_quantity_value=line.quantity_value,
                quantity_unit=line.quantity_unit,
                scaled_quantity_value=scaled_quantity,
                unit_price_value=line.unit_price_value,
                unit_price_unit=line.unit_price_unit,
                line_cost=line_cost,
                note=line.note,
                sort_order=line.sort_order,
            )
        )

    warnings: list[str] = []
    total_cost: Decimal | None
    if missing_price:
        total_cost = None
        warnings.append("cost incomplete; one or more ingredient lines missing price")
    else:
        total_cost = partial_total_cost

    cost_per_portion = (
        (total_cost / Decimal(target_portions)) if total_cost is not None else None
    )

    return RecipeCostBreakdown(
        recipe_id=recipe.recipe_id,
        target_portions=int(target_portions),
        source_yield_portions=source_yield_portions,
        scaled_lines=scaled_lines,
        total_cost=total_cost,
        cost_per_portion=cost_per_portion,
        warnings=warnings,
    )
