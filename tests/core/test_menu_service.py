from __future__ import annotations

import pytest

from core.components import Composition, InMemoryCompositionRepository
from core.menu import MenuService


def test_create_menu() -> None:
    service = MenuService()

    menu = service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    assert menu.menu_id == "menu_1"
    assert menu.site_id == "site_1"
    assert menu.week_key == "2026-W16"
    assert menu.version == 1
    assert menu.status == "draft"


def test_add_composition_based_menu_detail() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(
        Composition(
            composition_id="comp_1",
            composition_name="Plate",
        )
    )
    service = MenuService(composition_repository=composition_repo)
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    detail = service.add_menu_detail(
        menu_detail_id="d1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="composition",
        composition_id="comp_1",
        sort_order=10,
    )

    assert detail.composition_ref_type == "composition"
    assert detail.composition_id == "comp_1"
    assert detail.unresolved_text is None


def test_add_unresolved_menu_detail() -> None:
    service = MenuService()
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    detail = service.add_menu_detail(
        menu_detail_id="d1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="unresolved",
        unresolved_text="meatballs with mash",
        sort_order=10,
    )

    assert detail.composition_ref_type == "unresolved"
    assert detail.unresolved_text == "meatballs with mash"
    assert detail.composition_id is None


def test_invalid_mixed_states_rejected() -> None:
    service = MenuService()
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    with pytest.raises(ValueError, match="composition_id is required"):
        service.add_menu_detail(
            menu_detail_id="d1",
            menu_id="menu_1",
            day="monday",
            meal_slot="lunch",
            composition_ref_type="composition",
            composition_id=None,
            unresolved_text=None,
        )

    with pytest.raises(ValueError, match="unresolved_text is required"):
        service.add_menu_detail(
            menu_detail_id="d2",
            menu_id="menu_1",
            day="monday",
            meal_slot="lunch",
            composition_ref_type="unresolved",
            unresolved_text=None,
            composition_id=None,
        )

    with pytest.raises(ValueError, match="must be empty when composition_ref_type='composition'"):
        service.add_menu_detail(
            menu_detail_id="d3",
            menu_id="menu_1",
            day="monday",
            meal_slot="lunch",
            composition_ref_type="composition",
            composition_id="comp_1",
            unresolved_text="should-not-be-here",
        )

    with pytest.raises(ValueError, match="must be empty when composition_ref_type='unresolved'"):
        service.add_menu_detail(
            menu_detail_id="d4",
            menu_id="menu_1",
            day="monday",
            meal_slot="lunch",
            composition_ref_type="unresolved",
            unresolved_text="free text",
            composition_id="comp_1",
        )


def test_update_menu_detail_between_unresolved_and_composition() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(Composition(composition_id="comp_1", composition_name="Plate"))

    service = MenuService(composition_repository=composition_repo)
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    service.add_menu_detail(
        menu_detail_id="d1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="unresolved",
        unresolved_text="old text",
    )

    as_composition = service.update_menu_detail(
        menu_detail_id="d1",
        composition_ref_type="composition",
        composition_id="comp_1",
        unresolved_text="",
    )
    assert as_composition.composition_ref_type == "composition"
    assert as_composition.composition_id == "comp_1"
    assert as_composition.unresolved_text is None

    as_unresolved = service.update_menu_detail(
        menu_detail_id="d1",
        composition_ref_type="unresolved",
        unresolved_text="new text",
        composition_id="",
    )
    assert as_unresolved.composition_ref_type == "unresolved"
    assert as_unresolved.unresolved_text == "new text"
    assert as_unresolved.composition_id is None


def test_remove_menu_detail() -> None:
    service = MenuService()
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    service.add_menu_detail(
        menu_detail_id="d1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="unresolved",
        unresolved_text="row",
    )

    service.remove_menu_detail("d1")

    assert service.list_menu_details("menu_1") == []


def test_list_menu_details_in_documented_order() -> None:
    service = MenuService()
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    service.add_menu_detail(
        menu_detail_id="d3",
        menu_id="menu_1",
        day="tuesday",
        meal_slot="lunch",
        composition_ref_type="unresolved",
        unresolved_text="c",
        sort_order=10,
    )
    service.add_menu_detail(
        menu_detail_id="d2",
        menu_id="menu_1",
        day="monday",
        meal_slot="dinner",
        composition_ref_type="unresolved",
        unresolved_text="b",
        sort_order=20,
    )
    service.add_menu_detail(
        menu_detail_id="d1",
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_ref_type="unresolved",
        unresolved_text="a",
        sort_order=30,
    )

    rows = service.list_menu_details("menu_1")

    assert [row.menu_detail_id for row in rows] == ["d1", "d2", "d3"]


def test_composition_existence_validation_when_repository_injected() -> None:
    composition_repo = InMemoryCompositionRepository()
    service = MenuService(composition_repository=composition_repo)
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")

    with pytest.raises(ValueError, match="composition not found"):
        service.add_menu_detail(
            menu_detail_id="d1",
            menu_id="menu_1",
            day="monday",
            meal_slot="lunch",
            composition_ref_type="composition",
            composition_id="missing",
        )
