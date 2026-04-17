from __future__ import annotations

from decimal import Decimal

from core.builder import BuilderFlow
from core.components import (
    CompositionService,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
    Recipe,
    RecipeIngredientLine,
)
from core.menu import (
    ImportedMenuRow,
    InMemoryCompositionAliasRepository,
    MenuService,
    create_composition_alias,
)


def _build_flow() -> BuilderFlow:
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    composition_service = CompositionService(repository=composition_repository)
    menu_service = MenuService(composition_repository=composition_repository)

    return BuilderFlow(
        composition_service=composition_service,
        menu_service=menu_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
    )


def test_create_composition_and_add_components_through_builder_flow() -> None:
    flow = _build_flow()

    flow.create_composition(composition_id="plate", composition_name="Plate")
    updated = flow.add_component_to_composition(
        composition_id="plate",
        component_id="main_component",
        role="main",
        sort_order=10,
    )

    assert updated.composition_id == "plate"
    assert len(updated.components) == 1
    assert updated.components[0].component_id == "main_component"


def test_create_menu_and_import_rows_through_builder_flow() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Kottbullar med mos")
    create_composition_alias(
        alias_repository=flow._alias_repository,
        alias_id="a1",
        composition_id="plate",
        alias_text="Kottbullar m mos",
        composition_repository=flow._composition_repository,
    )

    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Kottbullar m mos")],
    )

    assert summary.imported_count == 1
    assert summary.resolved_count == 1
    assert summary.unresolved_count == 0


def test_list_unresolved_menu_details_works() -> None:
    flow = _build_flow()
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Unknown dish")],
    )

    unresolved = flow.list_unresolved_menu_details("menu_1")

    assert len(unresolved) == 1
    assert unresolved[0].composition_ref_type == "unresolved"
    assert unresolved[0].unresolved_text == "Unknown dish"


def test_menu_cost_overview_returns_resolved_and_unresolved_honestly() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Kottbullar med mos")
    flow.add_component_to_composition(
        composition_id="plate",
        component_id="plate",
        role="main",
        sort_order=10,
    )
    create_composition_alias(
        alias_repository=flow._alias_repository,
        alias_id="a1",
        composition_id="plate",
        alias_text="Kottbullar m mos",
        composition_repository=flow._composition_repository,
    )

    flow._recipe_repository.add_recipe(
        Recipe(
            recipe_id="r_plate",
            component_id="plate",
            recipe_name="Plate recipe",
            visibility="site",
            is_default=True,
            yield_portions=10,
        )
    )
    flow._ingredient_repository.add_ingredient_line(
        RecipeIngredientLine(
            recipe_ingredient_line_id="line_plate",
            recipe_id="r_plate",
            ingredient_name="Main ingredient",
            quantity_value=Decimal("100"),
            quantity_unit="g",
            unit_price_value=Decimal("0.1"),
            unit_price_unit="SEK/g",
            sort_order=10,
        )
    )

    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    flow.import_menu_rows(
        menu_id="menu_1",
        rows=[
            ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Kottbullar m mos", sort_order=10),
            ImportedMenuRow(day="monday", meal_slot="dinner", raw_text="Unknown dish", sort_order=20),
        ],
    )

    overview = flow.get_menu_cost_overview(menu_id="menu_1", default_target_portions=20)

    assert len(overview.detail_costs) == 2
    assert overview.unresolved_count == 1
    assert any(detail.total_cost == Decimal("20.0") for detail in overview.detail_costs)
    assert any(detail.total_cost is None for detail in overview.detail_costs)


def test_builder_flow_is_orchestration_not_logic_duplication() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Simple plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="no match")],
    )

    # The import flow should simply reflect existing resolution behavior (unresolved fallback).
    assert summary.unresolved_count == 1
    assert summary.row_results[0].kind == "unresolved"
