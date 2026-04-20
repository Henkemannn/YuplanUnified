from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .recipe_domain import Recipe, RecipeIngredientLine


@dataclass(frozen=True)
class ScaledRecipeIngredientLinePreview:
    recipe_ingredient_line_id: str
    ingredient_name: str
    amount_unit: str
    original_amount_value: Decimal
    scaled_amount_value: Decimal
    note: str | None
    sort_order: int


@dataclass(frozen=True)
class RecipeScalingPreview:
    recipe_id: str
    component_id: str
    recipe_name: str
    visibility: str
    notes: str | None
    source_yield_portions: int
    target_portions: int
    scaling_factor: Decimal
    ingredient_lines: list[ScaledRecipeIngredientLinePreview] = field(default_factory=list)


def calculate_recipe_scaling_preview(
    recipe: Recipe,
    ingredient_lines: list[RecipeIngredientLine],
    target_portions: int,
) -> RecipeScalingPreview:
    target = int(target_portions)
    if target <= 0:
        raise ValueError("target_portions must be > 0")

    source_yield = int(recipe.yield_portions)
    if source_yield <= 0:
        raise ValueError("recipe.yield_portions must be > 0")

    scaling_factor = Decimal(target) / Decimal(source_yield)

    scaled_lines: list[ScaledRecipeIngredientLinePreview] = []
    for line in ingredient_lines:
        scaled_lines.append(
            ScaledRecipeIngredientLinePreview(
                recipe_ingredient_line_id=line.recipe_ingredient_line_id,
                ingredient_name=line.ingredient_name,
                amount_unit=line.quantity_unit,
                original_amount_value=line.quantity_value,
                scaled_amount_value=line.quantity_value * scaling_factor,
                note=line.note,
                sort_order=line.sort_order,
            )
        )

    return RecipeScalingPreview(
        recipe_id=recipe.recipe_id,
        component_id=recipe.component_id,
        recipe_name=recipe.recipe_name,
        visibility=recipe.visibility,
        notes=recipe.notes,
        source_yield_portions=source_yield,
        target_portions=target,
        scaling_factor=scaling_factor,
        ingredient_lines=scaled_lines,
    )
