from __future__ import annotations

from pathlib import Path

from core.builder import BuilderFlow
from core.builder_menu_context_flow import BuilderMenuContextFlow
from core.builder_sqlite import (
    initialize_builder_sqlite,
    SQLiteComponentAliasRepository,
    SQLiteComponentRepository,
    SQLiteCompositionAliasRepository,
    SQLiteCompositionRepository,
    SQLiteMenuDetailRepository,
    SQLiteMenuRepository,
)
from core.components import ComponentService, CompositionService
from core.components import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository
from core.menu import MenuService


def _db_path(tmp_path: Path) -> str:
    db_path = tmp_path / "builder_persistence_test.db"
    initialize_builder_sqlite(str(db_path))
    return str(db_path)


def _build_builder_flow(db_path: str) -> BuilderFlow:
    component_repo = SQLiteComponentRepository(db_path=db_path)
    composition_repo = SQLiteCompositionRepository(db_path=db_path)
    component_alias_repo = SQLiteComponentAliasRepository(db_path=db_path)
    composition_alias_repo = SQLiteCompositionAliasRepository(db_path=db_path)

    return BuilderFlow(
        component_service=ComponentService(repository=component_repo),
        composition_service=CompositionService(repository=composition_repo),
        composition_repository=composition_repo,
        alias_repository=composition_alias_repo,
        component_alias_repository=component_alias_repo,
    )


def _build_menu_context_flow(builder_flow: BuilderFlow, db_path: str) -> BuilderMenuContextFlow:
    menu_service = MenuService(
        menu_repository=SQLiteMenuRepository(db_path=db_path),
        menu_detail_repository=SQLiteMenuDetailRepository(db_path=db_path),
        composition_repository=builder_flow._composition_repository,
    )
    return BuilderMenuContextFlow(
        menu_service=menu_service,
        composition_repository=builder_flow._composition_repository,
        alias_repository=builder_flow._alias_repository,
        recipe_repository=InMemoryRecipeRepository(),
        ingredient_repository=InMemoryRecipeIngredientLineRepository(),
        library_flow=builder_flow,
    )


def test_component_persists_after_repository_reload(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)

    repo_one = SQLiteComponentRepository(db_path=db_path)
    flow_one = _build_builder_flow(db_path)
    created = flow_one.create_standalone_component("Mashed Potatoes")

    repo_two = SQLiteComponentRepository(db_path=db_path)
    loaded = repo_two.get(created.component_id)

    assert loaded is not None
    assert loaded.component_id == created.component_id
    assert loaded.canonical_name == "Mashed Potatoes"
    assert repo_one.get(created.component_id) is not None


def test_alias_persists_after_reload(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    flow_one = _build_builder_flow(db_path)
    component = flow_one.create_standalone_component("Tomato Sauce")
    flow_one.add_component_alias(
        component_id=component.component_id,
        alias_text="Tomatsas",
        source="test",
    )

    flow_two = _build_builder_flow(db_path)
    aliases = flow_two.list_component_aliases(component_id=component.component_id)

    assert len(aliases) == 1
    assert aliases[0].alias_text == "Tomatsas"


def test_composition_with_component_links_persists(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    flow_one = _build_builder_flow(db_path)
    comp = flow_one.create_composition(composition_id="plate_1", composition_name="Fish plate")
    updated = flow_one.add_component_to_composition(
        composition_id=comp.composition_id,
        component_name="Fish",
        role="main",
    )

    flow_two = _build_builder_flow(db_path)
    loaded = flow_two._composition_repository.get(updated.composition_id)

    assert loaded is not None
    assert loaded.composition_name == "Fish plate"
    assert len(loaded.components) == 1
    assert loaded.components[0].component_name == "Fish"


def test_menu_with_rows_persists(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    flow_one = _build_builder_flow(db_path)
    flow_one.create_composition(composition_id="cmp_1", composition_name="Soup")
    menu_flow_one = _build_menu_context_flow(flow_one, db_path)

    menu_flow_one.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W17", title="Week 17")
    menu_flow_one.add_composition_menu_row(
        menu_id="menu_1",
        day="monday",
        meal_slot="lunch",
        composition_id="cmp_1",
    )

    flow_two = _build_builder_flow(db_path)
    menu_flow_two = _build_menu_context_flow(flow_two, db_path)
    rows = menu_flow_two.list_menu_rows("menu_1")

    assert len(rows) == 1
    assert rows[0]["composition_id"] == "cmp_1"
    assert rows[0]["day"] == "monday"


def test_import_created_items_remain_after_new_session(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    flow_one = _build_builder_flow(db_path)

    summary = flow_one.import_library_text_lines([
        "Kottbullar med potatismos",
        "Fiskgratang",
    ])

    assert summary.created_count == 2

    flow_two = _build_builder_flow(db_path)
    compositions = flow_two.list_library_compositions()
    components = flow_two.list_library_components()

    assert len(compositions) >= 2
    assert len(components) >= 2
    assert any(item.composition_name == "Fiskgratang" for item in compositions)
