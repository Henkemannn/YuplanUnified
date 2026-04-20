from __future__ import annotations

from core.components import (
    ComponentService,
    CompositionService,
    InMemoryComponentRepository,
    InMemoryCompositionRepository,
)
from core.menu import InMemoryMenuDetailRepository, InMemoryMenuRepository, MenuService
from core.planera_v2.adapters import build_menu_composition_grouped_payload
from core.planera_v2.adapters import build_menu_composition_payload


def _build_services() -> tuple[MenuService, CompositionService, InMemoryCompositionRepository]:
    composition_repository = InMemoryCompositionRepository()
    component_repository = InMemoryComponentRepository()
    component_service = ComponentService(repository=component_repository)
    composition_service = CompositionService(repository=composition_repository)

    menu_service = MenuService(
        menu_repository=InMemoryMenuRepository(),
        menu_detail_repository=InMemoryMenuDetailRepository(),
        composition_repository=composition_repository,
    )
    return menu_service, composition_service, composition_repository


def test_adapter_resolves_menu_row_to_composition_components_and_roles() -> None:
    menu_service, composition_service, composition_repository = _build_services()

    composition_service.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    composition_service.add_component_to_composition(
        composition_id="plate_1",
        component_id="fish",
        component_name="Fish",
        role="main",
        sort_order=10,
    )
    composition_service.add_component_to_composition(
        composition_id="plate_1",
        component_id="sauce",
        component_name="Dill Sauce",
        role="sauce",
        sort_order=20,
    )

    menu = menu_service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="plate_1",
        sort_order=10,
    )

    payload = build_menu_composition_payload(
        menu=menu,
        menu_details=menu_service.list_menu_details("menu_1"),
        composition_repository=composition_repository,
    )

    assert payload["menu"]["menu_id"] == "menu_1"
    assert payload["count"] == 1
    row = payload["rows"][0]
    assert row["menu_detail"]["menu_detail_id"] == "menu_1-row-1"
    assert row["resolution"]["kind"] == "composition"
    composition = row["resolution"]["composition"]
    assert composition["composition_id"] == "plate_1"
    assert [item["component_id"] for item in composition["components"]] == ["fish", "sauce"]
    assert [item["role"] for item in composition["components"]] == ["main", "sauce"]


def test_adapter_handles_unresolved_row_explicitly_and_safely() -> None:
    menu_service, _, composition_repository = _build_services()

    menu = menu_service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-2",
        menu_id="menu_1",
        day="monday",
        meal_slot="dinner",
        composition_ref_type="unresolved",
        unresolved_text="Unknown dish",
        sort_order=20,
    )

    payload = build_menu_composition_payload(
        menu=menu,
        menu_details=menu_service.list_menu_details("menu_1"),
        composition_repository=composition_repository,
    )

    row = payload["rows"][0]
    assert row["resolution"]["kind"] == "unresolved"
    assert row["resolution"]["composition"] is None
    assert row["resolution"]["unresolved_text"] == "Unknown dish"


def test_adapter_output_excludes_production_and_recipe_fields() -> None:
    menu_service, composition_service, composition_repository = _build_services()

    composition_service.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    composition_service.add_component_to_composition(
        composition_id="plate_1",
        component_id="fish",
        component_name="Fish",
        role=None,
        sort_order=10,
    )

    menu = menu_service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="plate_1",
        sort_order=10,
    )

    payload = build_menu_composition_payload(
        menu=menu,
        menu_details=menu_service.list_menu_details("menu_1"),
        composition_repository=composition_repository,
    )

    row = payload["rows"][0]
    forbidden_keys = {
        "quantity",
        "quantity_value",
        "ingredient",
        "ingredients",
        "recipe",
        "recipe_id",
        "target_portions",
        "total_cost",
    }
    assert forbidden_keys.isdisjoint(set(row["resolution"].keys()))
    composition = row["resolution"]["composition"] or {}
    assert forbidden_keys.isdisjoint(set(composition.keys()))


def test_adapter_can_filter_to_single_menu_detail() -> None:
    menu_service, composition_service, composition_repository = _build_services()

    composition_service.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    menu = menu_service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="plate_1",
        sort_order=10,
    )
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-2",
        menu_id="menu_1",
        day="monday",
        meal_slot="dinner",
        composition_ref_type="unresolved",
        unresolved_text="Unknown dish",
        sort_order=20,
    )

    payload = build_menu_composition_payload(
        menu=menu,
        menu_details=menu_service.list_menu_details("menu_1"),
        composition_repository=composition_repository,
        menu_detail_id="menu_1-row-2",
    )

    assert payload["count"] == 1
    assert payload["rows"][0]["menu_detail"]["menu_detail_id"] == "menu_1-row-2"


def test_grouped_adapter_groups_by_day_then_meal_with_resolved_components() -> None:
    menu_service, composition_service, composition_repository = _build_services()

    composition_service.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    composition_service.add_component_to_composition(
        composition_id="plate_1",
        component_id="fish",
        component_name="Fish",
        role="main",
        sort_order=10,
    )

    menu = menu_service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="plate_1",
        sort_order=10,
    )
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-2",
        menu_id="menu_1",
        day="monday",
        meal_slot="dinner",
        composition_ref_type="unresolved",
        unresolved_text="Unknown dish",
        sort_order=20,
    )

    payload = build_menu_composition_grouped_payload(
        menu=menu,
        menu_details=menu_service.list_menu_details("menu_1"),
        composition_repository=composition_repository,
    )

    assert payload["menu"]["menu_id"] == "menu_1"
    assert payload["count"] == 2
    days = payload["days"]
    assert len(days) == 1
    assert days[0]["day"] == "monday"
    meals = days[0]["meals"]
    assert [meal["meal_slot"] for meal in meals] == ["dinner", "lunch"]

    lunch_row = (next(meal for meal in meals if meal["meal_slot"] == "lunch")["rows"])[0]
    assert lunch_row["resolution"]["kind"] == "composition"
    composition = lunch_row["resolution"]["composition"]
    assert composition["composition_id"] == "plate_1"
    assert composition["components"][0]["role"] == "main"


def test_grouped_adapter_keeps_unresolved_rows_visible() -> None:
    menu_service, _, composition_repository = _build_services()

    menu = menu_service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-2",
        menu_id="menu_1",
        day="monday",
        meal_slot="dinner",
        composition_ref_type="unresolved",
        unresolved_text="Unknown dish",
        sort_order=20,
    )

    payload = build_menu_composition_grouped_payload(
        menu=menu,
        menu_details=menu_service.list_menu_details("menu_1"),
        composition_repository=composition_repository,
    )

    dinners = payload["days"][0]["meals"][0]["rows"]
    assert len(dinners) == 1
    assert dinners[0]["resolution"]["kind"] == "unresolved"
    assert dinners[0]["resolution"]["composition"] is None
    assert dinners[0]["resolution"]["unresolved_text"] == "Unknown dish"


def test_grouped_adapter_excludes_production_and_recipe_fields() -> None:
    menu_service, composition_service, composition_repository = _build_services()

    composition_service.create_composition(composition_id="plate_1", composition_name="Fish Plate")
    composition_service.add_component_to_composition(
        composition_id="plate_1",
        component_id="fish",
        component_name="Fish",
        role=None,
        sort_order=10,
    )
    menu = menu_service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    menu_service.add_menu_detail(
        menu_detail_id="menu_1-row-1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="plate_1",
        sort_order=10,
    )

    payload = build_menu_composition_grouped_payload(
        menu=menu,
        menu_details=menu_service.list_menu_details("menu_1"),
        composition_repository=composition_repository,
    )

    row = payload["days"][0]["meals"][0]["rows"][0]
    forbidden_keys = {
        "quantity",
        "quantity_value",
        "ingredient",
        "ingredients",
        "recipe",
        "recipe_id",
        "target_portions",
        "total_cost",
    }
    resolution = row["resolution"]
    assert forbidden_keys.isdisjoint(set(resolution.keys()))
    composition = resolution["composition"] or {}
    assert forbidden_keys.isdisjoint(set(composition.keys()))
