from __future__ import annotations

from decimal import Decimal

from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
    Recipe,
    RecipeIngredientLine,
)
from core.menu import ImportedMenuRow, InMemoryCompositionAliasRepository, MenuService, create_composition_alias


def _build_flows() -> tuple[BuilderFlow, BuilderMenuContextFlow]:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    recipe_repository = InMemoryRecipeRepository()
    ingredient_repository = InMemoryRecipeIngredientLineRepository()

    component_service = ComponentService(repository=component_repository)
    composition_service = CompositionService(repository=composition_repository)
    menu_service = MenuService(composition_repository=composition_repository)

    builder_flow = BuilderFlow(
        component_service=component_service,
        composition_service=composition_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
    )
    menu_context_flow = BuilderMenuContextFlow(
        menu_service=menu_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        library_flow=builder_flow,
    )
    return builder_flow, menu_context_flow


def test_create_menu_and_import_rows_through_menu_context_flow() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate", composition_name="Kottbullar med mos")
    create_composition_alias(
        alias_repository=builder_flow._alias_repository,
        alias_id="a1",
        composition_id="plate",
        alias_text="Kottbullar m mos",
        composition_repository=builder_flow._composition_repository,
    )

    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Kottbullar m mos")],
    )

    assert summary.imported_count == 1
    assert summary.resolved_count == 1
    assert summary.unresolved_count == 0


def test_add_composition_menu_row_stores_composition_reference_only() -> None:
    builder_flow, flow = _build_flows()
    created = builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16", title="Week menu")

    detail = flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id=created.composition_id,
        note="main course",
    )

    assert detail.menu_id == "menu_1"
    assert detail.composition_ref_type == "composition"
    assert detail.composition_id == "plate_1"
    assert detail.unresolved_text is None


def test_list_menu_rows_includes_linked_composition_name() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
    )

    rows = flow.list_menu_rows("menu_1")

    assert len(rows) == 1
    assert rows[0]["composition_ref_type"] == "composition"
    assert rows[0]["composition_id"] == "plate_1"
    assert rows[0]["composition_name"] == "Fish Plate"
    assert rows[0]["unresolved_text"] is None


def test_update_menu_row_changes_day_meal_note_composition_and_sort_order() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    builder_flow.create_composition(composition_id="plate_2", composition_name="Veg Plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    created = flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
        note="old",
        sort_order=5,
    )

    updated = flow.update_composition_menu_row(
        menu_id="menu_1",
        menu_detail_id=created.menu_detail_id,
        day="tuesday",
        meal_slot="dinner",
        composition_id="plate_2",
        note="updated",
        sort_order=1,
    )

    assert updated.day == "tuesday"
    assert updated.meal_slot == "dinner"
    assert updated.composition_ref_type == "composition"
    assert updated.composition_id == "plate_2"
    assert updated.unresolved_text is None
    assert updated.note == "updated"
    assert updated.sort_order == 1


def test_delete_menu_row_removes_row() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    created = flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
    )

    flow.delete_menu_row(menu_id="menu_1", menu_detail_id=created.menu_detail_id)

    rows = flow.list_menu_rows("menu_1")
    assert rows == []


def test_list_menu_rows_orders_by_sort_order_first() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="wednesday",
        meal_slot="dinner",
        composition_id="plate_1",
        sort_order=20,
    )
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
        sort_order=10,
    )

    rows = flow.list_menu_rows("menu_1")

    assert len(rows) == 2
    assert rows[0]["sort_order"] == 10
    assert rows[1]["sort_order"] == 20


def test_list_menu_rows_grouped_orders_deterministically_without_calendar_assumptions() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="wednesday",
        meal_slot="dinner",
        composition_id="plate_1",
        sort_order=30,
    )
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="dinner",
        composition_id="plate_1",
        sort_order=20,
    )
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
        sort_order=10,
    )

    groups = flow.list_menu_rows_grouped("menu_1")

    assert [
        (group["day"], group["meal_slot"])
        for group in groups
    ] == [("monday", "lunch"), ("monday", "dinner"), ("wednesday", "dinner")]


def test_list_menu_rows_grouped_keeps_row_sort_order_within_group() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
        sort_order=20,
        note="second",
    )
    flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
        sort_order=10,
        note="first",
    )

    groups = flow.list_menu_rows_grouped("menu_1")

    assert len(groups) == 1
    rows = groups[0]["rows"]
    assert [row["sort_order"] for row in rows] == [10, 20]
    assert [row["note"] for row in rows] == ["first", "second"]


def test_list_unresolved_menu_details_works() -> None:
    _, flow = _build_flows()
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
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate", composition_name="Kottbullar med mos")
    builder_flow.add_component_to_composition(
        composition_id="plate",
        component_name="Plate",
        role="main",
    )
    create_composition_alias(
        alias_repository=builder_flow._alias_repository,
        alias_id="a1",
        composition_id="plate",
        alias_text="Kottbullar m mos",
        composition_repository=builder_flow._composition_repository,
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


def test_menu_context_flow_is_orchestration_not_logic_duplication() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate", composition_name="Simple plate")
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="no match")],
    )

    assert summary.unresolved_count == 1
    assert summary.row_results[0].kind == "unresolved"


def test_create_composition_from_unresolved_row_creates_and_resolves() -> None:
    _, flow = _build_flows()
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    summary = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Unknown dish")],
    )
    detail_id = summary.row_results[0].menu_detail_id

    created, updated, warnings = flow.create_composition_from_unresolved_row(
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
    assert warnings == []


def test_create_composition_from_unresolved_row_adds_suggested_components() -> None:
    _, flow = _build_flows()
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

    created, _, _ = flow.create_composition_from_unresolved_row(
        menu_id="menu_1",
        menu_detail_id=detail_id,
        composition_name="Fiskratt",
    )

    component_ids = [item.component_id for item in created.components]
    assert component_ids == ["kokt_torsk", "aggsas", "pressad_potatis"]
    component_names = [item.component_name for item in created.components]
    assert component_names == ["Kokt torsk", "Äggsås", "Pressad potatis"]


def test_reimport_same_text_resolves_via_auto_created_alias() -> None:
    _, flow = _build_flows()
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    first = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="No Match")],
    )
    first_detail_id = first.row_results[0].menu_detail_id
    created, _, _ = flow.create_composition_from_unresolved_row(
        menu_id="menu_1",
        menu_detail_id=first_detail_id,
        composition_name="No Match Plate",
    )

    second = flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="tuesday", meal_slot="lunch", raw_text="No Match")],
    )

    assert second.resolved_count == 1
    assert second.unresolved_count == 0
    assert second.row_results[0].composition_id == created.composition_id


def test_menu_declaration_readiness_aggregates_signals_from_composition_rows() -> None:
    builder_flow, flow = _build_flows()
    builder_flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    with_component = builder_flow.add_component_to_composition(
        composition_id="plate_1",
        component_name="Fish",
        role="main",
    )
    component_id = with_component.components[0].component_id
    recipe = builder_flow.create_component_recipe(
        component_id=component_id,
        recipe_name="Fish Base",
        visibility="private",
        yield_portions=8,
    )
    builder_flow.add_recipe_ingredient_line(
        component_id=component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Cod",
        amount_value=500,
        amount_unit="g",
        trait_signals=["fish"],
    )

    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    created = flow.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="plate_1",
    )

    readiness = flow.get_menu_declaration_readiness("menu_1")

    assert readiness.menu_id == "menu_1"
    assert readiness.trait_signals_present == ("fish",)
    assert readiness.conflict_preview.conflicts_present == ("fish_relevant",)
    assert len(readiness.rows) == 1
    assert readiness.rows[0].menu_detail_id == created.menu_detail_id
    assert readiness.rows[0].composition_id == "plate_1"
    assert readiness.rows[0].trait_signals_present == ("fish",)
    assert readiness.rows[0].conflict_preview.conflicts_present == ("fish_relevant",)
    assert any("missing primary recipe" in message for message in readiness.rows[0].warnings)
    assert any("missing primary recipe" in message for message in readiness.warnings)


def test_menu_declaration_readiness_marks_unresolved_rows_without_automation() -> None:
    _, flow = _build_flows()
    flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    flow.import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="No Match")],
    )

    readiness = flow.get_menu_declaration_readiness("menu_1")

    assert readiness.trait_signals_present == ()
    assert readiness.conflict_preview.conflicts_present == ()
    assert len(readiness.rows) == 1
    assert readiness.rows[0].composition_ref_type == "unresolved"
    assert readiness.rows[0].components == []
    assert readiness.rows[0].warnings
    assert "unresolved menu row text: No Match" in readiness.rows[0].warnings[0]
