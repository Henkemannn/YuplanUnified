from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.builder.library_scope import ObjectScope
from core.builder_sqlite import BuilderObjectScopeRecord
from core.builder_sqlite import SQLiteBuilderObjectScopeRepository
from core.builder_sqlite import clear_builder_sqlite_data
from core.builder_sqlite import initialize_builder_sqlite


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_legacy_builder_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE builder_components (
                component_id TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL
            );

            CREATE TABLE builder_compositions (
                composition_id TEXT PRIMARY KEY,
                composition_name TEXT NOT NULL,
                library_group TEXT NULL
            );

            INSERT INTO builder_components (component_id, canonical_name)
            VALUES ('component-1', 'Soup Base');

            INSERT INTO builder_compositions (composition_id, composition_name, library_group)
            VALUES ('composition-1', 'Dinner Menu', 'ovrigt');
            """
        )


def _repository(path: Path) -> SQLiteBuilderObjectScopeRepository:
    return SQLiteBuilderObjectScopeRepository(db_path=initialize_builder_sqlite(str(path)))


def test_initialize_builder_sqlite_creates_scope_table_and_preserves_legacy_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "builder.sqlite3"
    _create_legacy_builder_db(db_path)

    initialize_builder_sqlite(str(db_path))

    with _connect(db_path) as conn:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'builder_object_scopes'"
        ).fetchone()
        component_count = conn.execute("SELECT COUNT(*) AS count FROM builder_components").fetchone()["count"]
        composition_count = conn.execute("SELECT COUNT(*) AS count FROM builder_compositions").fetchone()["count"]
        scope_count = conn.execute("SELECT COUNT(*) AS count FROM builder_object_scopes").fetchone()["count"]

    assert table_exists is not None
    assert int(component_count) == 1
    assert int(composition_count) == 1
    assert int(scope_count) == 0


def test_existing_legacy_rows_do_not_receive_automatic_scope(tmp_path: Path) -> None:
    db_path = tmp_path / "builder.sqlite3"
    _create_legacy_builder_db(db_path)

    initialize_builder_sqlite(str(db_path))

    with _connect(db_path) as conn:
        scope_count = conn.execute("SELECT COUNT(*) AS count FROM builder_object_scopes").fetchone()["count"]

    assert int(scope_count) == 0


def test_clear_builder_sqlite_data_clears_object_scopes(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )

    repo.set_scope("component", "component-1", scope)
    cleared = clear_builder_sqlite_data(str(tmp_path / "builder.sqlite3"))

    assert "builder_object_scopes" in cleared
    assert cleared["builder_object_scopes"] == 1
    assert repo.list_for_tenant(7) == []


def test_organisation_scope_round_trips(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )

    repo.set_scope("composition", "composition-1", scope)

    assert repo.get_scope("composition", "composition-1") == scope


def test_user_private_scope_round_trips(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    scope = ObjectScope(
        tenant_id=7,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="private",
        source_object_id=None,
    )

    repo.set_scope("component", "component-1", scope)

    stored = repo.get_scope("component", "component-1")
    assert stored == scope
    assert stored is not None
    assert stored.owner_user_id == 101
    assert stored.owner_site_id == "site-a"


def test_site_scope_round_trips(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    scope = ObjectScope(
        tenant_id=7,
        owner_scope="site",
        owner_site_id="site-a",
        owner_user_id=None,
        visibility="site",
        source_object_id=None,
    )

    repo.set_scope("composition", "composition-2", scope)

    assert repo.get_scope("composition", "composition-2") == scope


def test_source_object_id_lineage_round_trips(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="site",
        source_object_id="composition-001",
    )

    repo.set_scope("component", "component-2", scope)

    stored = repo.get_scope("component", "component-2")
    assert stored == scope
    assert stored is not None
    assert stored.source_object_id == "composition-001"


def test_set_scope_upserts_existing_scope(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    initial_scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )
    updated_scope = ObjectScope(
        tenant_id=7,
        owner_scope="site",
        owner_site_id="site-a",
        owner_user_id=None,
        visibility="site",
        source_object_id="composition-002",
    )

    repo.set_scope("component", "component-3", initial_scope)
    repo.set_scope("component", "component-3", updated_scope)

    assert repo.get_scope("component", "component-3") == updated_scope


def test_same_object_id_can_exist_for_component_and_composition(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    component_scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )
    composition_scope = ObjectScope(
        tenant_id=7,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="private",
        source_object_id="composition-7",
    )

    repo.set_scope("component", "shared-id", component_scope)
    repo.set_scope("composition", "shared-id", composition_scope)

    assert repo.get_scope("component", "shared-id") == component_scope
    assert repo.get_scope("composition", "shared-id") == composition_scope


def test_list_for_tenant_never_returns_another_tenant_scope(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    tenant_one_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )
    tenant_two_scope = ObjectScope(
        tenant_id=2,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )

    repo.set_scope("component", "component-10", tenant_one_scope)
    repo.set_scope("composition", "composition-20", tenant_two_scope)

    listed = repo.list_for_tenant(1)
    assert listed == [
        BuilderObjectScopeRecord(
            object_type="component",
            object_id="component-10",
            scope=tenant_one_scope,
        )
    ]
    assert all(item.scope.tenant_id == 1 for item in listed)


def test_object_type_filtering_works(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    component_scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )
    composition_scope = ObjectScope(
        tenant_id=7,
        owner_scope="site",
        owner_site_id="site-a",
        owner_user_id=None,
        visibility="site",
        source_object_id=None,
    )

    repo.set_scope("component", "component-1", component_scope)
    repo.set_scope("composition", "composition-1", composition_scope)

    assert repo.list_for_tenant(7, "component") == [
        BuilderObjectScopeRecord(
            object_type="component",
            object_id="component-1",
            scope=component_scope,
        )
    ]
    assert repo.list_for_tenant(7, "composition") == [
        BuilderObjectScopeRecord(
            object_type="composition",
            object_id="composition-1",
            scope=composition_scope,
        )
    ]


def test_list_for_tenant_preserves_object_identity_and_ordering(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    first_scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )
    second_scope = ObjectScope(
        tenant_id=7,
        owner_scope="site",
        owner_site_id="site-a",
        owner_user_id=None,
        visibility="site",
        source_object_id="composition-10",
    )

    repo.set_scope("composition", "composition-b", second_scope)
    repo.set_scope("component", "component-a", first_scope)

    listed = repo.list_for_tenant(7)

    assert listed == [
        BuilderObjectScopeRecord(object_type="component", object_id="component-a", scope=first_scope),
        BuilderObjectScopeRecord(object_type="composition", object_id="composition-b", scope=second_scope),
    ]
    assert [item.object_type for item in listed] == ["component", "composition"]
    assert [item.object_id for item in listed] == ["component-a", "composition-b"]


def test_delete_scope_removes_only_requested_scope(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    component_scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )
    composition_scope = ObjectScope(
        tenant_id=7,
        owner_scope="site",
        owner_site_id="site-a",
        owner_user_id=None,
        visibility="site",
        source_object_id=None,
    )

    repo.set_scope("component", "shared-id", component_scope)
    repo.set_scope("composition", "shared-id", composition_scope)

    repo.delete_scope("component", "shared-id")

    assert repo.get_scope("component", "shared-id") is None
    assert repo.get_scope("composition", "shared-id") == composition_scope


def test_invalid_object_type_raises_value_error(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )

    with pytest.raises(ValueError):
        repo.set_scope("dish", "object-1", scope)
    with pytest.raises(ValueError):
        repo.get_scope("dish", "object-1")
    with pytest.raises(ValueError):
        repo.list_for_tenant(7, "dish")
    with pytest.raises(ValueError):
        repo.delete_scope("dish", "object-1")


def test_empty_object_id_raises_value_error(tmp_path: Path) -> None:
    repo = _repository(tmp_path / "builder.sqlite3")
    scope = ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )

    with pytest.raises(ValueError):
        repo.set_scope("component", "", scope)
    with pytest.raises(ValueError):
        repo.get_scope("component", "")
    with pytest.raises(ValueError):
        repo.delete_scope("component", "")
