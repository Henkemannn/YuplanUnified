from __future__ import annotations

from decimal import Decimal

import pytest

from core.components import Recipe, RecipeIngredientLine, calculate_recipe_cost_breakdown


def _recipe(*, yield_portions: int = 10) -> Recipe:
    return Recipe(
        recipe_id="r_meatballs",
        component_id="meatballs",
        recipe_name="Meatballs Base",
        visibility="site",
        yield_portions=yield_portions,
    )


def test_scale_recipe_from_10_to_20_portions() -> None:
    recipe = _recipe(yield_portions=10)
    lines = [
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_1",
            recipe_id=recipe.recipe_id,
            ingredient_name="Potato",
            quantity_value=Decimal("900"),
            quantity_unit="g",
            sort_order=10,
        )
    ]

    breakdown = calculate_recipe_cost_breakdown(recipe, lines, target_portions=20)

    assert breakdown.source_yield_portions == 10
    assert breakdown.target_portions == 20
    assert breakdown.scaled_lines[0].original_quantity_value == Decimal("900")
    assert breakdown.scaled_lines[0].scaled_quantity_value == Decimal("1800")


def test_cost_calculation_with_all_prices_present() -> None:
    recipe = _recipe(yield_portions=10)
    lines = [
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_1",
            recipe_id=recipe.recipe_id,
            ingredient_name="Potato",
            quantity_value=Decimal("900"),
            quantity_unit="g",
            unit_price_value=Decimal("0.02"),
            unit_price_unit="SEK/g",
            sort_order=10,
        ),
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_2",
            recipe_id=recipe.recipe_id,
            ingredient_name="Salt",
            quantity_value=Decimal("10"),
            quantity_unit="g",
            unit_price_value=Decimal("0.01"),
            unit_price_unit="SEK/g",
            sort_order=20,
        ),
    ]

    breakdown = calculate_recipe_cost_breakdown(recipe, lines, target_portions=20)

    assert breakdown.scaled_lines[0].line_cost == Decimal("36.00")
    assert breakdown.scaled_lines[1].line_cost == Decimal("0.20")
    assert breakdown.total_cost == Decimal("36.20")
    assert breakdown.cost_per_portion == Decimal("1.81")
    assert breakdown.warnings == []


def test_incomplete_cost_when_one_line_lacks_price() -> None:
    recipe = _recipe(yield_portions=10)
    lines = [
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_1",
            recipe_id=recipe.recipe_id,
            ingredient_name="Potato",
            quantity_value=Decimal("900"),
            quantity_unit="g",
            unit_price_value=Decimal("0.02"),
            unit_price_unit="SEK/g",
            sort_order=10,
        ),
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_2",
            recipe_id=recipe.recipe_id,
            ingredient_name="Butter",
            quantity_value=Decimal("50"),
            quantity_unit="g",
            unit_price_value=None,
            sort_order=20,
        ),
    ]

    breakdown = calculate_recipe_cost_breakdown(recipe, lines, target_portions=20)

    assert breakdown.scaled_lines[0].line_cost == Decimal("36.00")
    assert breakdown.scaled_lines[1].line_cost is None
    assert breakdown.total_cost is None
    assert breakdown.cost_per_portion is None
    assert breakdown.warnings == ["cost incomplete; one or more ingredient lines missing price"]


def test_invalid_target_portions_rejected() -> None:
    recipe = _recipe(yield_portions=10)

    with pytest.raises(ValueError, match="target_portions must be > 0"):
        calculate_recipe_cost_breakdown(recipe, [], target_portions=0)


def test_invalid_recipe_yield_rejected_defensively() -> None:
    recipe = _recipe(yield_portions=0)

    with pytest.raises(ValueError, match="recipe.yield_portions must be > 0"):
        calculate_recipe_cost_breakdown(recipe, [], target_portions=10)


def test_preserve_ingredient_order() -> None:
    recipe = _recipe(yield_portions=10)
    lines = [
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_2",
            recipe_id=recipe.recipe_id,
            ingredient_name="Second",
            quantity_value=Decimal("2"),
            quantity_unit="kg",
            sort_order=20,
        ),
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_1",
            recipe_id=recipe.recipe_id,
            ingredient_name="First",
            quantity_value=Decimal("1"),
            quantity_unit="kg",
            sort_order=10,
        ),
    ]

    breakdown = calculate_recipe_cost_breakdown(recipe, lines, target_portions=10)

    assert [line.ingredient_name for line in breakdown.scaled_lines] == ["Second", "First"]


def test_decimal_behavior_stable_for_fractional_scaling() -> None:
    recipe = _recipe(yield_portions=3)
    lines = [
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_1",
            recipe_id=recipe.recipe_id,
            ingredient_name="Cream",
            quantity_value=Decimal("1.5"),
            quantity_unit="l",
            unit_price_value=Decimal("2.4"),
            unit_price_unit="SEK/l",
            sort_order=10,
        ),
    ]

    breakdown = calculate_recipe_cost_breakdown(recipe, lines, target_portions=2)

    assert breakdown.scaled_lines[0].scaled_quantity_value == Decimal("1.0")
    assert breakdown.total_cost == Decimal("2.40")
    assert breakdown.cost_per_portion == Decimal("1.20")
