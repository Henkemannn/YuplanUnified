from __future__ import annotations

import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

import core.builder_sqlite as builder_sqlite
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
    BuilderSchemaError,
    require_builder_sqlite,
)
from core.components import ComponentService, Composition, CompositionComponent, CompositionService
from core.components import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository
from core.menu import MenuService


def _db_path(tmp_path: Path) -> str:
    db_path = tmp_path / "builder_persistence_test.db"
    initialize_builder_sqlite(str(db_path))
    return str(db_path)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_legacy_composition_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE builder_compositions (
                composition_id TEXT PRIMARY KEY,
                composition_name TEXT NOT NULL,
                library_group TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE builder_composition_components (
                composition_id TEXT NOT NULL,
                component_id TEXT NOT NULL,
                component_name TEXT NULL,
                role TEXT NULL,
                sort_order INTEGER NOT NULL,
                PRIMARY KEY (composition_id, component_id, sort_order),
                FOREIGN KEY(composition_id) REFERENCES builder_compositions(composition_id),
                FOREIGN KEY(component_id) REFERENCES builder_components(component_id)
            );
            """
        )


def _create_legacy_menu_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE builder_menus (
                menu_id TEXT PRIMARY KEY,
                title TEXT NULL,
                site_id TEXT NOT NULL,
                week_key TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE builder_menu_rows (
                menu_detail_id TEXT PRIMARY KEY,
                menu_id TEXT NOT NULL,
                day TEXT NOT NULL,
                meal_slot TEXT NOT NULL,
                composition_ref_type TEXT NOT NULL,
                composition_id TEXT NULL,
                unresolved_text TEXT NULL,
                note TEXT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(menu_id) REFERENCES builder_menus(menu_id),
                FOREIGN KEY(composition_id) REFERENCES builder_compositions(composition_id)
            );
            """
        )


def test_missing_builder_schema_does_not_create_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"
    with pytest.raises(BuilderSchemaError, match="explicit provisioning"):
        require_builder_sqlite(str(path))
    assert not path.exists()


def test_builder_provisioning_cli_requires_confirmation(tmp_path: Path) -> None:
    path = tmp_path / "builder.db"
    command = [sys.executable, "-m", "scripts.provision_builder_sqlite", "--database", str(path)]
    denied = subprocess.run(command, capture_output=True, text=True, check=False)
    assert denied.returncode != 0
    assert not path.exists()
    result = subprocess.run(command + ["--confirm-schema-upgrade"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert require_builder_sqlite(str(path)) == str(path)


def test_repeated_builder_provisioning_preserves_existing_data(tmp_path: Path) -> None:
    path = tmp_path / "builder.db"
    initialize_builder_sqlite(str(path))
    with _connect(path) as conn:
        conn.execute("INSERT INTO builder_components(component_id, canonical_name) VALUES('c1', 'Synthetic')")
        conn.execute(
            "INSERT INTO builder_object_scopes(object_type, object_id, tenant_id, owner_scope, owner_site_id, visibility) "
            "VALUES('component', 'c1', 1, 'site', 'site-1', 'site')"
        )
        conn.commit()
        before = list(conn.iterdump())
    initialize_builder_sqlite(str(path))
    with _connect(path) as conn:
        assert list(conn.iterdump()) == before


@pytest.mark.parametrize(
    ("table", "column", "column_type"),
    [
        ("builder_object_scopes", "tenant_id", "INTEGER"),
        ("builder_object_scopes", "object_type", "TEXT"),
        ("builder_components", "canonical_name", "TEXT"),
        ("builder_menu_rows", "row_kind", "TEXT"),
        ("builder_import_session_items", "selected", "INTEGER"),
    ],
)
def test_builder_schema_rejects_nullable_required_columns(tmp_path: Path, table, column, column_type) -> None:
    path = tmp_path / "builder.db"
    initialize_builder_sqlite(str(path))
    with closing(_connect(path)) as conn:
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()["sql"]
        required = f"{column} {column_type} NOT NULL"
        assert sql.count(required) == 1
        conn.execute(f"DROP TABLE {table}")
        conn.execute(sql.replace(required, f"{column} {column_type} NULL"))
        conn.commit()
        before = list(conn.iterdump())

    with pytest.raises(BuilderSchemaError, match=rf"{table}\.{column}"):
        require_builder_sqlite(str(path))
    with closing(_connect(path)) as conn:
        assert list(conn.iterdump()) == before


def test_canonical_builder_schema_allows_nullable_columns_and_text_primary_keys(tmp_path: Path) -> None:
    path = tmp_path / "builder.db"
    initialize_builder_sqlite(str(path))
    with closing(_connect(path)) as conn:
        scopes = {row["name"]: row for row in conn.execute("PRAGMA table_info('builder_object_scopes')")}
        components = {row["name"]: row for row in conn.execute("PRAGMA table_info('builder_components')")}
        assert scopes["owner_site_id"]["notnull"] == 0
        assert scopes["owner_user_id"]["notnull"] == 0
        assert scopes["source_object_id"]["notnull"] == 0
        assert components["component_id"]["pk"] == 1
        assert components["component_id"]["notnull"] == 0
    assert require_builder_sqlite(str(path)) == str(path)


def test_all_canonical_required_columns_reject_nullable_schema(tmp_path: Path) -> None:
    path = tmp_path / "builder.db"
    initialize_builder_sqlite(str(path))
    with closing(_connect(path)) as canonical:
        for table in builder_sqlite._REQUIRED_COLUMNS:
            sql = canonical.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()["sql"]
            for column in canonical.execute(f"PRAGMA table_info('{table}')"):
                if not column["notnull"]:
                    continue
                name = column["name"]
                declaration = f'{name} {column["type"]} NOT NULL'
                assert sql.count(declaration) == 1
                with closing(sqlite3.connect(":memory:")) as probe:
                    canonical.backup(probe)
                    probe.row_factory = sqlite3.Row
                    probe.execute(f"DROP TABLE {table}")
                    probe.execute(sql.replace(declaration, f'{name} {column["type"]} NULL'))
                    with pytest.raises(BuilderSchemaError, match=rf"{table}\.{name}"):
                        builder_sqlite._check_builder_schema(probe)


def test_builder_provisioning_rejects_nullable_scope_and_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    _create_legacy_menu_db(path)
    with closing(_connect(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE builder_object_scopes (
                object_type TEXT NOT NULL, object_id TEXT NOT NULL, tenant_id INTEGER NULL,
                owner_scope TEXT NOT NULL, owner_site_id TEXT NULL, owner_user_id INTEGER NULL,
                visibility TEXT NOT NULL, source_object_id TEXT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (object_type, object_id)
            );
            INSERT INTO builder_object_scopes VALUES (
                'component', 'synthetic', NULL, 'site', 'site-1', NULL, 'site', NULL, 'before', 'before'
            );
            INSERT INTO builder_menus(menu_id, site_id, week_key) VALUES('menu-1', 'site-1', '2026-W15');
            INSERT INTO builder_menu_rows(menu_detail_id, menu_id, day, meal_slot, composition_ref_type)
                VALUES('row-1', 'menu-1', 'monday', 'lunch', 'unresolved');
            """
        )
        before = list(conn.iterdump())

    with pytest.raises(BuilderSchemaError, match=r"builder_object_scopes\.tenant_id"):
        initialize_builder_sqlite(str(path))
    with closing(_connect(path)) as conn:
        assert list(conn.iterdump()) == before


def test_builder_schema_without_category_uniqueness_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "builder.db"
    initialize_builder_sqlite(str(path))
    with _connect(path) as conn:
        conn.executescript(
            """
            DROP TABLE builder_dish_categories;
            CREATE TABLE builder_dish_categories (
                category_id TEXT PRIMARY KEY, tenant_id INTEGER NOT NULL, site_id TEXT NOT NULL,
                display_name TEXT NOT NULL, name_norm TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """
        )
    with pytest.raises(BuilderSchemaError, match="category uniqueness"):
        require_builder_sqlite(str(path))


def test_builder_schema_upgrade_failure_rolls_back_schema_and_data(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "legacy.db"
    _create_legacy_menu_db(path)
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO builder_menus(menu_id, site_id, week_key) VALUES('menu-1', 'site-1', '2026-W15')"
        )
        conn.execute(
            "INSERT INTO builder_menu_rows(menu_detail_id, menu_id, day, meal_slot, composition_ref_type) "
            "VALUES('row-1', 'menu-1', 'monday', 'lunch', 'unresolved')"
        )
        conn.commit()
        before = list(conn.iterdump())

    def fail(_conn):
        raise BuilderSchemaError("injected provisioning failure")

    monkeypatch.setattr(builder_sqlite, "_validate_builder_schema", fail)
    with pytest.raises(BuilderSchemaError, match="injected provisioning failure"):
        initialize_builder_sqlite(str(path))
    with _connect(path) as conn:
        assert list(conn.iterdump()) == before


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
    comp = flow_one.create_composition(
        composition_id="plate_1",
        composition_name="Fish plate",
        use_custom_menu_name=True,
        menu_name="Custom fish plate",
    )
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
    assert loaded.use_custom_menu_name is True
    assert loaded.menu_name == "Custom fish plate"


def test_legacy_composition_schema_upgrade_adds_custom_menu_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_builder_persistence_test.db"
    _create_legacy_composition_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO builder_compositions(composition_id, composition_name, library_group) "
            "VALUES('existing-dish', 'Synthetic legacy dish', 'fisk')"
        )
        conn.commit()

    initialize_builder_sqlite(str(db_path))

    with _connect(db_path) as conn:
        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info('builder_compositions')").fetchall()}
        row = conn.execute(
            "SELECT composition_name, library_group FROM builder_compositions WHERE composition_id='existing-dish'"
        ).fetchone()

    assert "use_custom_menu_name" in columns
    assert "menu_name" in columns
    assert "menu_nameTEXT" not in columns
    assert tuple(row) == ("Synthetic legacy dish", "fisk")

    repo = SQLiteCompositionRepository(db_path=str(db_path))
    created = Composition(
        composition_id="plate_upgrade",
        composition_name="Lasagne",
        library_group="ovrigt",
        components=[],
        use_custom_menu_name=True,
        menu_name="Test menu name",
    )
    repo.add(created)

    loaded = repo.get("plate_upgrade")
    assert loaded is not None
    assert loaded.use_custom_menu_name is True
    assert loaded.menu_name == "Test menu name"
    assert loaded.effective_menu_name == "Test menu name"


def test_legacy_menu_row_schema_upgrade_adds_display_label_and_row_kind(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_builder_menu_rows_test.db"
    _create_legacy_menu_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("INSERT INTO builder_menus(menu_id, site_id, week_key) VALUES('old-menu', 'old-site', '2026-W15')")
        conn.execute(
            "INSERT INTO builder_menu_rows(menu_detail_id, menu_id, day, meal_slot, composition_ref_type, unresolved_text) "
            "VALUES('old-row', 'old-menu', 'monday', 'lunch', 'unresolved', 'Synthetic legacy row')"
        )
        conn.commit()

    initialize_builder_sqlite(str(db_path))

    with _connect(db_path) as conn:
        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info('builder_menu_rows')").fetchall()}
        row = conn.execute(
            "SELECT m.site_id, r.menu_id, r.unresolved_text FROM builder_menu_rows r "
            "JOIN builder_menus m ON r.menu_id=m.menu_id WHERE r.menu_detail_id='old-row'"
        ).fetchone()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    assert "display_label" in columns
    assert "row_kind" in columns
    assert tuple(row) == ("old-site", "old-menu", "Synthetic legacy row")

    builder_flow = _build_builder_flow(str(db_path))
    menu_flow = _build_menu_context_flow(builder_flow, str(db_path))
    menu_flow.create_menu(menu_id="menu_1", site_id="site_1", week_key="2026-W17")
    created = menu_flow.create_empty_menu_row(
        menu_id="menu_1",
        day="monday",
        display_label="Farmors favorit",
    )

    loaded = menu_flow.list_menu_rows("menu_1")[0]
    assert loaded["menu_detail_id"] == created.menu_detail_id
    assert loaded["display_label"] == "Farmors favorit"
    assert loaded["row_kind"] == "dynamic"


def test_composition_menu_name_round_trips(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    repo = SQLiteCompositionRepository(db_path=db_path)
    composition = Composition(
        composition_id="plate_custom",
        composition_name="Lasagne",
        library_group="ovrigt",
        components=[],
        use_custom_menu_name=True,
        menu_name="Hemlagad lasagne",
    )

    repo.add(composition)
    loaded = repo.get("plate_custom")

    assert loaded is not None
    assert loaded.use_custom_menu_name is True
    assert loaded.menu_name == "Hemlagad lasagne"
    assert loaded.effective_menu_name == "Hemlagad lasagne"


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
