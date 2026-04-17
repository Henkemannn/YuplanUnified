from __future__ import annotations

from decimal import Decimal

import pytest

from core.components import RecipeService


def test_create_recipe() -> None:
    service = RecipeService()

    recipe = service.create_recipe(
        recipe_id="r_meatballs_default",
        component_id="meatballs",
        recipe_name="Meatballs Base",
        visibility="site",
        yield_portions=100,
    )

    assert recipe.recipe_id == "r_meatballs_default"
    assert recipe.component_id == "meatballs"
    assert recipe.visibility == "site"
    assert recipe.is_default is False
    assert recipe.yield_portions == 100


def test_multiple_recipes_per_component() -> None:
    service = RecipeService()
    service.create_recipe(
        recipe_id="r1",
        component_id="fish_timbal",
        recipe_name="Fish Timbal Base",
        visibility="tenant",
        yield_portions=40,
    )
    service.create_recipe(
        recipe_id="r2",
        component_id="fish_timbal",
        recipe_name="Fish Timbal Vegan",
        visibility="tenant",
        yield_portions=40,
    )

    recipes = service.list_recipes_for_component("fish_timbal")

    assert {recipe.recipe_id for recipe in recipes} == {"r1", "r2"}


def test_default_recipe_switching() -> None:
    service = RecipeService()
    service.create_recipe(
        recipe_id="r1",
        component_id="potato_gratin",
        recipe_name="Gratin A",
        visibility="site",
        yield_portions=60,
        is_default=True,
    )
    service.create_recipe(
        recipe_id="r2",
        component_id="potato_gratin",
        recipe_name="Gratin B",
        visibility="site",
        yield_portions=60,
    )

    updated = service.set_default_recipe(component_id="potato_gratin", recipe_id="r2")

    assert updated.is_default is True
    r1 = service.get_recipe("r1")
    r2 = service.get_recipe("r2")
    assert r1 is not None and r1.is_default is False
    assert r2 is not None and r2.is_default is True


def test_invalid_visibility_rejected() -> None:
    service = RecipeService()

    with pytest.raises(ValueError, match="invalid visibility"):
        service.create_recipe(
            recipe_id="r1",
            component_id="meatballs",
            recipe_name="Bad Visibility",
            visibility="global",
            yield_portions=10,
        )


def test_invalid_yield_rejected() -> None:
    service = RecipeService()

    with pytest.raises(ValueError, match="yield_portions must be > 0"):
        service.create_recipe(
            recipe_id="r1",
            component_id="meatballs",
            recipe_name="No Yield",
            visibility="private",
            yield_portions=0,
        )


def test_add_ingredient_lines() -> None:
    service = RecipeService()
    recipe = service.create_recipe(
        recipe_id="r_meatballs",
        component_id="meatballs",
        recipe_name="Meatballs Base",
        visibility="site",
        yield_portions=20,
    )

    line = service.add_ingredient_line(
        recipe_ingredient_line_id="line_1",
        recipe_id=recipe.recipe_id,
        ingredient_name="Potato",
        quantity_value=900,
        quantity_unit="g",
        unit_price_value=18.5,
        unit_price_unit="SEK/kg",
    )

    assert line.recipe_id == recipe.recipe_id
    assert line.quantity_value == Decimal("900")
    assert line.quantity_unit == "g"
    assert line.unit_price_value == Decimal("18.5")


def test_missing_or_empty_unit_rejected() -> None:
    service = RecipeService()
    recipe = service.create_recipe(
        recipe_id="r1",
        component_id="meatballs",
        recipe_name="Base",
        visibility="private",
        yield_portions=10,
    )

    with pytest.raises(ValueError, match="quantity_unit"):
        service.add_ingredient_line(
            recipe_ingredient_line_id="line_1",
            recipe_id=recipe.recipe_id,
            ingredient_name="Salt",
            quantity_value=10,
            quantity_unit="",
        )


def test_non_positive_quantity_rejected() -> None:
    service = RecipeService()
    recipe = service.create_recipe(
        recipe_id="r1",
        component_id="meatballs",
        recipe_name="Base",
        visibility="private",
        yield_portions=10,
    )

    with pytest.raises(ValueError, match="quantity_value must be > 0"):
        service.add_ingredient_line(
            recipe_ingredient_line_id="line_1",
            recipe_id=recipe.recipe_id,
            ingredient_name="Salt",
            quantity_value=0,
            quantity_unit="g",
        )


def test_list_ingredient_lines_in_sort_order() -> None:
    service = RecipeService()
    recipe = service.create_recipe(
        recipe_id="r1",
        component_id="fish_timbal",
        recipe_name="Fish Timbal Base",
        visibility="site",
        yield_portions=12,
    )

    service.add_ingredient_line(
        recipe_ingredient_line_id="line_2",
        recipe_id=recipe.recipe_id,
        ingredient_name="Salt",
        quantity_value=5,
        quantity_unit="g",
        sort_order=20,
    )
    service.add_ingredient_line(
        recipe_ingredient_line_id="line_1",
        recipe_id=recipe.recipe_id,
        ingredient_name="Fish",
        quantity_value=1.2,
        quantity_unit="kg",
        sort_order=10,
    )

    lines = service.list_ingredient_lines(recipe.recipe_id)

    assert [line.recipe_ingredient_line_id for line in lines] == ["line_1", "line_2"]
