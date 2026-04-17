from __future__ import annotations

from core.components import Composition, InMemoryCompositionRepository
from core.menu import (
    ImportedMenuRow,
    InMemoryCompositionAliasRepository,
    MenuService,
    create_composition_alias,
    import_menu_rows,
)


def _setup_menu_service_with_menu(composition_repo: InMemoryCompositionRepository) -> MenuService:
    service = MenuService(composition_repository=composition_repo)
    service.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W16")
    return service


def test_import_fully_resolved_rows() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(Composition(composition_id="comp_a", composition_name="Kottbullar med mos"))
    composition_repo.add(Composition(composition_id="comp_b", composition_name="Fisk med potatis"))

    alias_repo = InMemoryCompositionAliasRepository()
    create_composition_alias(
        alias_repository=alias_repo,
        alias_id="a1",
        composition_id="comp_a",
        alias_text="Kottbullar m mos",
        composition_repository=composition_repo,
    )

    menu_service = _setup_menu_service_with_menu(composition_repo)
    rows = [
        ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Kottbullar m mos", sort_order=10),
        ImportedMenuRow(day="tuesday", meal_slot="lunch", raw_text="Fisk m potatis", sort_order=20),
    ]

    summary = import_menu_rows(
        menu_id="menu_1",
        rows=rows,
        menu_service=menu_service,
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert summary.imported_count == 2
    assert summary.resolved_count == 2
    assert summary.unresolved_count == 0
    assert summary.warnings == []
    assert [row.kind for row in summary.row_results] == ["composition", "composition"]


def test_import_unresolved_rows_preserves_text() -> None:
    composition_repo = InMemoryCompositionRepository()
    alias_repo = InMemoryCompositionAliasRepository()
    menu_service = _setup_menu_service_with_menu(composition_repo)

    rows = [
        ImportedMenuRow(
            day="monday",
            meal_slot="lunch",
            raw_text="Unknown dish text",
            sort_order=10,
        )
    ]

    summary = import_menu_rows(
        menu_id="menu_1",
        rows=rows,
        menu_service=menu_service,
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert summary.imported_count == 1
    assert summary.resolved_count == 0
    assert summary.unresolved_count == 1
    assert summary.row_results[0].kind == "unresolved"
    assert summary.row_results[0].unresolved_text == "Unknown dish text"
    assert summary.warnings == ["one or more imported rows are unresolved"]


def test_mixed_batch_import_and_summary_counts() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(Composition(composition_id="comp_a", composition_name="Kottbullar med mos"))
    alias_repo = InMemoryCompositionAliasRepository()
    create_composition_alias(
        alias_repository=alias_repo,
        alias_id="a1",
        composition_id="comp_a",
        alias_text="Kottbullar m mos",
        composition_repository=composition_repo,
    )

    menu_service = _setup_menu_service_with_menu(composition_repo)
    rows = [
        ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Kottbullar m mos", sort_order=10),
        ImportedMenuRow(day="monday", meal_slot="dinner", raw_text="Unknown text", sort_order=20),
    ]

    summary = import_menu_rows(
        menu_id="menu_1",
        rows=rows,
        menu_service=menu_service,
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert summary.imported_count == 2
    assert summary.resolved_count == 1
    assert summary.unresolved_count == 1
    assert [row.kind for row in summary.row_results] == ["composition", "unresolved"]


def test_menu_details_are_created_via_menu_service() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(Composition(composition_id="comp_a", composition_name="Dish A"))
    alias_repo = InMemoryCompositionAliasRepository()
    create_composition_alias(
        alias_repository=alias_repo,
        alias_id="a1",
        composition_id="comp_a",
        alias_text="Dish A",
        composition_repository=composition_repo,
    )
    menu_service = _setup_menu_service_with_menu(composition_repo)

    summary = import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Dish A", sort_order=10)],
        menu_service=menu_service,
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    details = menu_service.list_menu_details("menu_1")
    assert len(details) == 1
    assert details[0].menu_detail_id == summary.row_results[0].menu_detail_id
    assert details[0].composition_ref_type == "composition"


def test_repeated_imports_are_stable_and_create_new_rows() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(Composition(composition_id="comp_a", composition_name="Dish A"))
    alias_repo = InMemoryCompositionAliasRepository()
    create_composition_alias(
        alias_repository=alias_repo,
        alias_id="a1",
        composition_id="comp_a",
        alias_text="Dish A",
        composition_repository=composition_repo,
    )
    menu_service = _setup_menu_service_with_menu(composition_repo)

    first = import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="monday", meal_slot="lunch", raw_text="Dish A", sort_order=10)],
        menu_service=menu_service,
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )
    second = import_menu_rows(
        menu_id="menu_1",
        rows=[ImportedMenuRow(day="tuesday", meal_slot="lunch", raw_text="Dish A", sort_order=10)],
        menu_service=menu_service,
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert first.row_results[0].menu_detail_id != second.row_results[0].menu_detail_id
    assert len(menu_service.list_menu_details("menu_1")) == 2
