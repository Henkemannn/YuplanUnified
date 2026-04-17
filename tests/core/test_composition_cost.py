from __future__ import annotations

from decimal import Decimal

from core.components import (
    Composition,
    CompositionComponent,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
    Recipe,
    RecipeIngredientLine,
    calculate_composition_cost,
)


def _build_repositories() -> tuple[InMemoryRecipeRepository, InMemoryRecipeIngredientLineRepository]:
    return InMemoryRecipeRepository(), InMemoryRecipeIngredientLineRepository()


def test_composition_with_two_valid_components_calculates_total() -> None:
    recipe_repo, ingredient_repo = _build_repositories()

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_main",
            component_id="meatballs",
            recipe_name="Meatballs Base",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="l_main",
            recipe_id="r_main",
            ingredient_name="Meat",
            quantity_value=Decimal("100"),
            quantity_unit="g",
            unit_price_value=Decimal("0.1"),
            unit_price_unit="SEK/g",
            sort_order=10,
        )
    )

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_side",
            component_id="potatoes",
            recipe_name="Potato Base",
            visibility="site",
            is_default=True,
            yield_portions=5,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="l_side",
            recipe_id="r_side",
            ingredient_name="Potato",
            quantity_value=Decimal("50"),
            quantity_unit="g",
            unit_price_value=Decimal("0.2"),
            unit_price_unit="SEK/g",
            sort_order=10,
        )
    )

    composition = Composition(
        composition_id="comp_1",
        composition_name="Meatballs plate",
        components=[
            CompositionComponent(component_id="meatballs", role="main", sort_order=10),
            CompositionComponent(component_id="potatoes", role="side", sort_order=20),
        ],
    )

    breakdown = calculate_composition_cost(
        composition=composition,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=20,
    )

    assert len(breakdown.component_breakdowns) == 2
    assert breakdown.component_breakdowns[0].scaled_cost == Decimal("20.0")
    assert breakdown.component_breakdowns[1].scaled_cost == Decimal("40.0")
    assert breakdown.total_cost == Decimal("60.0")
    assert breakdown.cost_per_portion == Decimal("3.0")
    assert breakdown.warnings == []


def test_missing_default_recipe_for_component_makes_total_unknown() -> None:
    recipe_repo, ingredient_repo = _build_repositories()

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_main",
            component_id="meatballs",
            recipe_name="Meatballs Base",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="l_main",
            recipe_id="r_main",
            ingredient_name="Meat",
            quantity_value=Decimal("100"),
            quantity_unit="g",
            unit_price_value=Decimal("0.1"),
            unit_price_unit="SEK/g",
            sort_order=10,
        )
    )

    # Exists but not marked as default on purpose.
    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_sauce",
            component_id="sauce",
            recipe_name="Sauce Base",
            visibility="site",
            is_default=False,
            yield_portions=10,
        )
    )

    composition = Composition(
        composition_id="comp_1",
        composition_name="Meatballs plate",
        components=[
            CompositionComponent(component_id="meatballs", role="main", sort_order=10),
            CompositionComponent(component_id="sauce", role="sauce", sort_order=20),
        ],
    )

    breakdown = calculate_composition_cost(
        composition=composition,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=20,
    )

    assert breakdown.component_breakdowns[0].scaled_cost == Decimal("20.0")
    assert breakdown.component_breakdowns[1].scaled_cost is None
    assert breakdown.total_cost is None
    assert breakdown.cost_per_portion is None
    assert "missing default recipe for component: sauce" in breakdown.warnings


def test_incomplete_recipe_cost_propagates_to_composition_and_total_unknown() -> None:
    recipe_repo, ingredient_repo = _build_repositories()

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_main",
            component_id="meatballs",
            recipe_name="Meatballs Base",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="l_main",
            recipe_id="r_main",
            ingredient_name="Meat",
            quantity_value=Decimal("100"),
            quantity_unit="g",
            unit_price_value=Decimal("0.1"),
            unit_price_unit="SEK/g",
            sort_order=10,
        )
    )

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_side",
            component_id="potatoes",
            recipe_name="Potato Base",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="l_side",
            recipe_id="r_side",
            ingredient_name="Potato",
            quantity_value=Decimal("200"),
            quantity_unit="g",
            unit_price_value=None,
            unit_price_unit=None,
            sort_order=10,
        )
    )

    composition = Composition(
        composition_id="comp_1",
        composition_name="Meatballs plate",
        components=[
            CompositionComponent(component_id="meatballs", role="main", sort_order=10),
            CompositionComponent(component_id="potatoes", role="side", sort_order=20),
        ],
    )

    breakdown = calculate_composition_cost(
        composition=composition,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=10,
    )

    assert breakdown.component_breakdowns[0].scaled_cost == Decimal("10.0")
    assert breakdown.component_breakdowns[1].scaled_cost is None
    assert breakdown.total_cost is None
    assert any(
        warning == "component potatoes: cost incomplete; one or more ingredient lines missing price"
        for warning in breakdown.warnings
    )


def test_component_order_is_preserved() -> None:
    recipe_repo, ingredient_repo = _build_repositories()

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_a",
            component_id="a",
            recipe_name="A",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )
    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_b",
            component_id="b",
            recipe_name="B",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )

    composition = Composition(
        composition_id="comp_order",
        composition_name="Order",
        components=[
            CompositionComponent(component_id="b", sort_order=20),
            CompositionComponent(component_id="a", sort_order=10),
        ],
    )

    breakdown = calculate_composition_cost(
        composition=composition,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=10,
    )

    assert [item.component_id for item in breakdown.component_breakdowns] == ["b", "a"]


def test_correct_scaling_across_components() -> None:
    recipe_repo, ingredient_repo = _build_repositories()

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_main",
            component_id="main",
            recipe_name="Main",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="l_main",
            recipe_id="r_main",
            ingredient_name="MainIngredient",
            quantity_value=Decimal("30"),
            quantity_unit="g",
            unit_price_value=Decimal("1.5"),
            unit_price_unit="SEK/g",
            sort_order=10,
        )
    )

    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_side",
            component_id="side",
            recipe_name="Side",
            visibility="site",
            is_default=True,
            yield_portions=30,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="l_side",
            recipe_id="r_side",
            ingredient_name="SideIngredient",
            quantity_value=Decimal("60"),
            quantity_unit="g",
            unit_price_value=Decimal("0.5"),
            unit_price_unit="SEK/g",
            sort_order=10,
        )
    )

    composition = Composition(
        composition_id="comp_scale",
        composition_name="Scale",
        components=[
            CompositionComponent(component_id="main", role="main", sort_order=10),
            CompositionComponent(component_id="side", role="side", sort_order=20),
        ],
    )

    breakdown = calculate_composition_cost(
        composition=composition,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=15,
    )

    # main: factor 1.5 -> 30*1.5*1.5 = 67.5
    # side: factor 0.5 -> 60*0.5*0.5 = 15
    assert breakdown.component_breakdowns[0].scaled_cost == Decimal("67.50")
    assert breakdown.component_breakdowns[1].scaled_cost == Decimal("15.00")
    assert breakdown.total_cost == Decimal("82.50")
    assert breakdown.cost_per_portion == Decimal("5.50")
