from __future__ import annotations

from dataclasses import dataclass, field

from .recipe_domain import Recipe, RecipeIngredientLine


@dataclass(frozen=True)
class RecipeIngredientTraitSignalLine:
    recipe_ingredient_line_id: str
    ingredient_name: str
    amount_unit: str
    note: str | None
    trait_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecipeTraitSignalPreview:
    recipe_id: str
    component_id: str
    recipe_name: str
    trait_signals_present: tuple[str, ...] = ()
    ingredient_lines: list[RecipeIngredientTraitSignalLine] = field(default_factory=list)


def build_recipe_trait_signal_preview(
    recipe: Recipe,
    ingredient_lines: list[RecipeIngredientLine],
) -> RecipeTraitSignalPreview:
    seen: set[str] = set()
    for line in ingredient_lines:
        for signal in line.trait_signals:
            signal_value = str(signal or "").strip().lower()
            if signal_value:
                seen.add(signal_value)

    lines = [
        RecipeIngredientTraitSignalLine(
            recipe_ingredient_line_id=line.recipe_ingredient_line_id,
            ingredient_name=line.ingredient_name,
            amount_unit=line.quantity_unit,
            note=line.note,
            trait_signals=tuple(line.trait_signals),
        )
        for line in ingredient_lines
    ]

    return RecipeTraitSignalPreview(
        recipe_id=recipe.recipe_id,
        component_id=recipe.component_id,
        recipe_name=recipe.recipe_name,
        trait_signals_present=tuple(sorted(seen)),
        ingredient_lines=lines,
    )
