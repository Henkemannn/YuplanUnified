from __future__ import annotations

from decimal import Decimal
import pytest

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
        component_name="Main component",
        role="main",
    )

    assert updated.composition_id == "plate"
    assert len(updated.components) == 1
    assert updated.components[0].component_id == "main_component"


def test_remove_component_from_composition_through_builder_flow() -> None:
    flow = _build_flow()

    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="component",
    )
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Potatoes",
        role="component",
    )

    updated = flow.remove_component_from_composition(
        composition_id="plate",
        component_id="fish",
    )

    assert [item.component_id for item in updated.components] == ["potatoes"]


def test_rename_component_in_composition_through_builder_flow() -> None:
    flow = _build_flow()

    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="connector",
    )
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Potatoes",
        role="component",
    )

    updated = flow.rename_component_in_composition(
        composition_id="plate",
        component_id="fish",
        new_component_name="Salmon",
    )

    component_ids = [item.component_id for item in updated.components]
    assert component_ids == ["salmon", "potatoes"]
    assert updated.components[0].role == "connector"
    assert updated.components[0].sort_order == 10


def test_rename_component_in_composition_rejects_empty_name() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="component",
    )

    with pytest.raises(ValueError, match="component_name must be non-empty"):
        flow.rename_component_in_composition(
            composition_id="plate",
            component_id="fish",
            new_component_name="   ",
        )


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
        component_name="Plate",
        role="main",
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


def test_create_composition_from_unresolved_row_creates_and_resolves() -> None:
    flow = _build_flow()
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Unknown dish")],
    )
    detail_id = summary.row_results[0].menu_detail_id

    created, updated = flow.create_composition_from_unresolved_row(
        menu_id="menu_1",
        menu_detail_id=detail_id,
        composition_name="New Plate",
    )

    assert created.composition_id.startswith("cmp_")
    assert len(created.composition_id) == 10
    assert updated.menu_detail_id == detail_id
    assert updated.composition_ref_type == "composition"
    assert updated.composition_id == created.composition_id
    assert updated.unresolved_text is None


def test_create_composition_from_unresolved_row_adds_suggested_components() -> None:
    flow = _build_flow()
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[
            ImportedMenuRow(
                day="monday",
                meal_slot="lunch",
                raw_text="Kokt torsk med äggsås och pressad potatis",
            )
        ],
    )
    detail_id = summary.row_results[0].menu_detail_id

    created, _ = flow.create_composition_from_unresolved_row(
        menu_id="menu_1",
        menu_detail_id=detail_id,
        composition_name="Fiskratt",
    )

    component_ids = [item.component_id for item in created.components]
    assert component_ids == ["kokt_torsk", "aggsas", "pressad_potatis"]


def test_swedish_suggestions_preserve_display_names_and_normalize_ids() -> None:
    flow = _build_flow()
    raw_text = "Köttbullar med gräddsås och rödbetor"

    display_names = flow._suggest_components_from_unresolved_text(raw_text)
    assert display_names == ["Köttbullar", "Gräddsås", "Rödbetor"]

    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text=raw_text)],
    )
    detail_id = summary.row_results[0].menu_detail_id

    created, _ = flow.create_composition_from_unresolved_row(
        menu_id="menu_1",
        menu_detail_id=detail_id,
        composition_name="Svensk plate",
    )

    component_ids = [item.component_id for item in created.components]
    assert component_ids == ["kottbullar", "graddsas", "rodbetor"]
