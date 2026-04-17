from __future__ import annotations

from decimal import Decimal

from core.components import (
    Composition,
    CompositionComponent,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
    Recipe,
    RecipeIngredientLine,
)
from core.menu import MenuDetail, calculate_menu_detail_cost


def _seed_valid_component_recipe(
    recipe_repo: InMemoryRecipeRepository,
    ingredient_repo: InMemoryRecipeIngredientLineRepository,
    *,
    recipe_id: str,
    component_id: str,
    yield_portions: int,
    quantity_value: str,
    unit_price_value: str | None,
) -> None:
    recipe_repo.add_recipe(
        Recipe(
            recipe_id=recipe_id,
            component_id=component_id,
            recipe_name=f"{component_id} recipe",
            visibility="site",
            is_default=True,
            yield_portions=yield_portions,
        )
    )
    ingredient_repo.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id=f"line_{recipe_id}",
            recipe_id=recipe_id,
            ingredient_name=f"{component_id}_ingredient",
            quantity_value=Decimal(quantity_value),
            quantity_unit="g",
            unit_price_value=Decimal(unit_price_value) if unit_price_value is not None else None,
            unit_price_unit="SEK/g" if unit_price_value is not None else None,
            sort_order=10,
        )
    )


def test_resolved_menu_detail_with_valid_composition_returns_cost() -> None:
    composition_repo = InMemoryCompositionRepository()
    recipe_repo = InMemoryRecipeRepository()
    ingredient_repo = InMemoryRecipeIngredientLineRepository()

    composition_repo.add(
        Composition(
            composition_id="comp_plate",
            composition_name="Plate",
            components=[
                CompositionComponent(component_id="main", role="main", sort_order=10),
                CompositionComponent(component_id="side", role="side", sort_order=20),
            ],
        )
    )

    _seed_valid_component_recipe(
        recipe_repo,
        ingredient_repo,
        recipe_id="r_main",
        component_id="main",
        yield_portions=10,
        quantity_value="100",
        unit_price_value="0.1",
    )
    _seed_valid_component_recipe(
        recipe_repo,
        ingredient_repo,
        recipe_id="r_side",
        component_id="side",
        yield_portions=10,
        quantity_value="50",
        unit_price_value="0.2",
    )

    menu_detail = MenuDetail(
        menu_detail_id="md_1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="comp_plate",
    )

    result = calculate_menu_detail_cost(
        menu_detail=menu_detail,
        composition_repository=composition_repo,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=20,
    )

    assert result.total_cost == Decimal("40.0")
    assert result.cost_per_portion == Decimal("2.0")
    assert result.warnings == []


def test_unresolved_menu_detail_returns_warning_and_unknown_cost() -> None:
    composition_repo = InMemoryCompositionRepository()
    recipe_repo = InMemoryRecipeRepository()
    ingredient_repo = InMemoryRecipeIngredientLineRepository()

    menu_detail = MenuDetail(
        menu_detail_id="md_1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="unresolved",
        unresolved_text="meatballs with something",
    )

    result = calculate_menu_detail_cost(
        menu_detail=menu_detail,
        composition_repository=composition_repo,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=20,
    )

    assert result.total_cost is None
    assert result.cost_per_portion is None
    assert result.warnings == ["menu detail unresolved; composition cost unavailable"]


def test_missing_composition_returns_warning_and_unknown_cost() -> None:
    composition_repo = InMemoryCompositionRepository()
    recipe_repo = InMemoryRecipeRepository()
    ingredient_repo = InMemoryRecipeIngredientLineRepository()

    menu_detail = MenuDetail(
        menu_detail_id="md_1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="missing_comp",
    )

    result = calculate_menu_detail_cost(
        menu_detail=menu_detail,
        composition_repository=composition_repo,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=20,
    )

    assert result.total_cost is None
    assert result.cost_per_portion is None
    assert result.warnings == ["composition not found for menu detail"]


def test_missing_default_recipe_propagates_to_menu_cost() -> None:
    composition_repo = InMemoryCompositionRepository()
    recipe_repo = InMemoryRecipeRepository()
    ingredient_repo = InMemoryRecipeIngredientLineRepository()

    composition_repo.add(
        Composition(
            composition_id="comp_plate",
            composition_name="Plate",
            components=[
                CompositionComponent(component_id="main", role="main", sort_order=10),
                CompositionComponent(component_id="sauce", role="sauce", sort_order=20),
            ],
        )
    )

    _seed_valid_component_recipe(
        recipe_repo,
        ingredient_repo,
        recipe_id="r_main",
        component_id="main",
        yield_portions=10,
        quantity_value="100",
        unit_price_value="0.1",
    )

    # Recipe exists but is not default.
    recipe_repo.add_recipe(
        Recipe(
            recipe_id="r_sauce",
            component_id="sauce",
            recipe_name="Sauce",
            visibility="site",
            is_default=False,
            yield_portions=10,
        )
    )

    menu_detail = MenuDetail(
        menu_detail_id="md_1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="comp_plate",
    )

    result = calculate_menu_detail_cost(
        menu_detail=menu_detail,
        composition_repository=composition_repo,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=20,
    )

    assert result.total_cost is None
    assert result.cost_per_portion is None
    assert "missing default recipe for component: sauce" in result.warnings


def test_target_portions_flows_menu_to_composition_cost() -> None:
    composition_repo = InMemoryCompositionRepository()
    recipe_repo = InMemoryRecipeRepository()
    ingredient_repo = InMemoryRecipeIngredientLineRepository()

    composition_repo.add(
        Composition(
            composition_id="comp_plate",
            composition_name="Plate",
            components=[
                CompositionComponent(component_id="main", role="main", sort_order=10),
            ],
        )
    )

    _seed_valid_component_recipe(
        recipe_repo,
        ingredient_repo,
        recipe_id="r_main",
        component_id="main",
        yield_portions=10,
        quantity_value="10",
        unit_price_value="1",
    )

    menu_detail = MenuDetail(
        menu_detail_id="md_1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="comp_plate",
    )

    result = calculate_menu_detail_cost(
        menu_detail=menu_detail,
        composition_repository=composition_repo,
        recipe_repository=recipe_repo,
        ingredient_repository=ingredient_repo,
        target_portions=25,
    )

    assert result.target_portions == 25
    assert result.total_cost == Decimal("25")
    assert result.cost_per_portion == Decimal("1")
