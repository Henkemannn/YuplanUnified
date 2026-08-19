from __future__ import annotations

from pathlib import Path

import pytest

from core.app_factory import create_app
from core.builder import BuilderFlow
from core.builder.library_scope import ActorContext
from core.builder.library_scope import ObjectScope
from core.builder.library_scope import can_read_object
from core.builder_sqlite import SQLiteBuilderObjectScopeRepository
from core.builder_sqlite import initialize_builder_sqlite
from core.components import ComponentService
from core.components import CompositionService
from core.components import InMemoryComponentAliasRepository
from core.components import InMemoryComponentRepository
from core.components import InMemoryCompositionRepository
from core.menu import InMemoryCompositionAliasRepository


class _MemoryScopeRepository:
    def __init__(self, *, fail_on_set: bool = False) -> None:
        self.fail_on_set = fail_on_set
        self.scopes: dict[tuple[str, str], ObjectScope] = {}
        self.set_calls = 0

    def get_scope(self, object_type: str, object_id: str) -> ObjectScope | None:
        return self.scopes.get((object_type, object_id))

    def set_scope(self, object_type: str, object_id: str, scope: ObjectScope) -> None:
        self.set_calls += 1
        if self.fail_on_set:
            raise RuntimeError("scope persistence failed")
        self.scopes[(object_type, object_id)] = scope

    def delete_scope(self, object_type: str, object_id: str) -> None:
        self.scopes.pop((object_type, object_id), None)


def _actor(*, tenant_id: int = 1, user_id: int = 11, role: str = "admin") -> ActorContext:
    return ActorContext(tenant_id=tenant_id, user_id=user_id, site_id=None, role=role)


def _build_flow(scope_repository: object | None = None) -> BuilderFlow:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()
    component_alias_repository = InMemoryComponentAliasRepository()

    return BuilderFlow(
        component_service=ComponentService(repository=component_repository),
        composition_service=CompositionService(repository=composition_repository),
        composition_repository=composition_repository,
        alias_repository=alias_repository,
        component_alias_repository=component_alias_repository,
        object_scope_repository=scope_repository,  # type: ignore[arg-type]
    )


def _sqlite_client(tmp_path: Path):
    db_path = tmp_path / "builder_scope_flow.db"
    app = create_app({"TESTING": True, "BUILDER_DB_PATH": str(db_path)})
    initialize_builder_sqlite(str(db_path))
    return app.test_client(), str(db_path)


def test_create_scoped_component_persists_organisation_scope() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    actor = _actor(tenant_id=7, user_id=101)

    component = flow.create_standalone_component("Tomatsoppa", actor=actor)

    assert component.component_id == "tomatsoppa"
    assert scope_repo.get_scope("component", component.component_id) == ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )


def test_create_scoped_composition_persists_organisation_scope() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    actor = _actor(tenant_id=7, user_id=101)

    composition = flow.create_composition_with_generated_id("Free dish", actor=actor)

    assert composition.composition_name == "Free dish"
    assert scope_repo.get_scope("composition", composition.composition_id) == ObjectScope(
        tenant_id=7,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )


def test_seeded_components_receive_scope() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    actor = _actor(tenant_id=9, user_id=202)

    composition = flow.create_composition_with_generated_id(
        "Pannbiff med potatis",
        seed_components=True,
        actor=actor,
    )

    assert composition.components
    for linked in composition.components:
        scope = scope_repo.get_scope("component", linked.component_id)
        assert scope is not None
        assert scope.tenant_id == 9
        assert scope.owner_scope == "organisation"
        assert scope.visibility == "organisation"


def test_reused_object_keeps_existing_scope() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    actor = _actor(tenant_id=4, user_id=404)

    component = flow.create_standalone_component("Kokt potatis")
    existing_scope = ObjectScope(
        tenant_id=4,
        owner_scope="private",
        owner_site_id=None,
        owner_user_id=404,
        visibility="private",
        source_object_id=None,
    )
    scope_repo.set_scope("component", component.component_id, existing_scope)

    reused = flow.create_standalone_component("Kokt potatis", actor=actor)

    assert reused.component_id == component.component_id
    assert scope_repo.get_scope("component", component.component_id) == existing_scope
    assert scope_repo.set_calls == 1


@pytest.mark.parametrize("object_type", ["component", "composition"])
def test_scoped_objects_are_visible_only_within_tenant(object_type: str) -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    same_tenant = _actor(tenant_id=11, user_id=1)
    other_tenant = _actor(tenant_id=22, user_id=2)

    if object_type == "component":
        object_id = flow.create_standalone_component("Soppa", actor=same_tenant).component_id
        visible_same = flow.list_library_components(actor=same_tenant)
        visible_other = flow.list_library_components(actor=other_tenant)
    else:
        object_id = flow.create_composition("plate-1", "Plate", actor=same_tenant).composition_id
        visible_same = flow.list_library_compositions(actor=same_tenant)
        visible_other = flow.list_library_compositions(actor=other_tenant)

    assert object_id in {item.component_id if object_type == "component" else item.composition_id for item in visible_same}
    assert object_id not in {item.component_id if object_type == "component" else item.composition_id for item in visible_other}


@pytest.mark.parametrize("object_type", ["component", "composition"])
def test_private_object_is_only_visible_to_owner(object_type: str) -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=13, user_id=313)
    other_user = _actor(tenant_id=13, user_id=999)

    if object_type == "component":
        object_id = flow.create_standalone_component("Privat sak", actor=owner).component_id
    else:
        object_id = flow.create_composition("plate-private", "Private plate", actor=owner).composition_id

    scope_repo.set_scope(
        object_type,
        object_id,
        ObjectScope(
            tenant_id=13,
            owner_scope="user",
            owner_site_id=None,
            owner_user_id=313,
            visibility="private",
            source_object_id=None,
        ),
    )

    readable_owner = can_read_object(owner, scope_repo.get_scope(object_type, object_id))
    readable_other = can_read_object(other_user, scope_repo.get_scope(object_type, object_id))

    assert readable_owner is True
    assert readable_other is False

    if object_type == "component":
        assert object_id in {item.component_id for item in flow.list_library_components(actor=owner)}
        assert object_id not in {item.component_id for item in flow.list_library_components(actor=other_user)}
    else:
        assert object_id in {item.composition_id for item in flow.list_library_compositions(actor=owner)}
        assert object_id not in {item.composition_id for item in flow.list_library_compositions(actor=other_user)}


@pytest.mark.parametrize("object_type", ["component", "composition"])
def test_legacy_unscoped_objects_remain_visible(object_type: str) -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    actor = _actor(tenant_id=31, user_id=1)
    other_actor = _actor(tenant_id=32, user_id=2)

    if object_type == "component":
        object_id = flow.create_standalone_component("Legacy visible").component_id
        assert object_id in {item.component_id for item in flow.list_library_components(actor=actor)}
        assert object_id in {item.component_id for item in flow.list_library_components(actor=other_actor)}
    else:
        object_id = flow.create_composition("legacy-plate", "Legacy plate").composition_id
        assert object_id in {item.composition_id for item in flow.list_library_compositions(actor=actor)}
        assert object_id in {item.composition_id for item in flow.list_library_compositions(actor=other_actor)}


def test_builder_flow_without_scope_repo_preserves_legacy_behavior() -> None:
    flow = _build_flow()
    actor = _actor()

    component = flow.create_standalone_component("Legacy soup", actor=actor)
    composition = flow.create_composition_with_generated_id("Legacy dish", actor=actor)

    assert component.component_id == "legacy_soup"
    assert composition.composition_name == "Legacy dish"
    assert [item.component_id for item in flow.list_library_components(actor=actor)] == ["legacy_soup"]
    assert [item.composition_id for item in flow.list_library_compositions(actor=actor)] == [composition.composition_id]


def test_scoped_component_recipe_list_and_detail_are_blocked_for_foreign_tenant() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=51, user_id=501)
    foreign = _actor(tenant_id=52, user_id=502)

    component = flow.create_standalone_component("Recipe soup", actor=owner)
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Primary recipe",
        yield_portions=4,
    )

    with pytest.raises(ValueError, match="component not found"):
        flow.list_component_recipes(component_id=component.component_id, actor=foreign)

    with pytest.raises(ValueError, match="component not found"):
        flow.get_component_recipe_detail(
            component_id=component.component_id,
            recipe_id=recipe.recipe_id,
            actor=foreign,
        )

    same_tenant_component, same_tenant_recipes = flow.list_component_recipes(
        component_id=component.component_id,
        actor=owner,
    )
    assert same_tenant_component.component_id == component.component_id
    assert [item.recipe_id for item in same_tenant_recipes] == [recipe.recipe_id]

    detail_recipe, detail_lines = flow.get_component_recipe_detail(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        actor=owner,
    )
    assert detail_recipe.recipe_id == recipe.recipe_id
    assert detail_lines == []


def test_scoped_declaration_readiness_is_blocked_for_foreign_tenant() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=61, user_id=601)
    foreign = _actor(tenant_id=62, user_id=602)

    component = flow.create_standalone_component("Declaration soup", actor=owner)
    composition = flow.create_composition("plate-declaration", "Declaration plate", actor=owner)

    component_ready = flow.preview_component_declaration_readiness(component_id=component.component_id, actor=owner)
    composition_ready = flow.preview_composition_declaration_readiness(
        composition_id=composition.composition_id,
        actor=owner,
    )

    assert component_ready.component_id == component.component_id
    assert composition_ready.composition_id == composition.composition_id

    with pytest.raises(ValueError, match="component not found"):
        flow.preview_component_declaration_readiness(component_id=component.component_id, actor=foreign)

    with pytest.raises(ValueError, match="composition not found"):
        flow.preview_composition_declaration_readiness(
            composition_id=composition.composition_id,
            actor=foreign,
        )


def test_composition_declaration_readiness_forwards_actor_to_linked_components() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=63, user_id=603)
    foreign = _actor(tenant_id=63, user_id=604)

    component = flow.create_standalone_component("Nested readiness component", actor=owner)
    composition = flow.create_composition("nested-readiness-plate", "Nested readiness plate", actor=owner)
    scope_repo.set_scope(
        "component",
        component.component_id,
        ObjectScope(
            tenant_id=63,
            owner_scope="user",
            owner_site_id=None,
            owner_user_id=603,
            visibility="private",
            source_object_id=None,
        ),
    )
    flow.attach_existing_component_to_composition(
        composition_id=composition.composition_id,
        component_id=component.component_id,
        actor=owner,
    )

    with pytest.raises(ValueError, match="component not found"):
        flow.preview_composition_declaration_readiness(
            composition_id=composition.composition_id,
            actor=foreign,
        )


def test_legacy_unscoped_objects_remain_readable_for_recipe_and_declaration_paths() -> None:
    flow = _build_flow()
    actor = _actor(tenant_id=71, user_id=701)
    component = flow.create_standalone_component("Legacy recipe component")
    composition = flow.create_composition("legacy-read-plate", "Legacy read plate")

    listed_component, recipes = flow.list_component_recipes(component_id=component.component_id, actor=actor)
    assert listed_component.component_id == component.component_id
    assert recipes == []

    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Legacy recipe",
        yield_portions=2,
    )
    detail_recipe, detail_lines = flow.get_component_recipe_detail(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        actor=actor,
    )
    assert detail_recipe.recipe_id == recipe.recipe_id
    assert detail_lines == []

    component_ready = flow.preview_component_declaration_readiness(component_id=component.component_id, actor=actor)
    composition_ready = flow.preview_composition_declaration_readiness(
        composition_id=composition.composition_id,
        actor=actor,
    )
    assert component_ready.component_id == component.component_id
    assert composition_ready.composition_id == composition.composition_id


def test_scope_persistence_failure_rolls_back_component_creation() -> None:
    scope_repo = _MemoryScopeRepository(fail_on_set=True)
    flow = _build_flow(scope_repo)
    actor = _actor()

    with pytest.raises(RuntimeError, match="scope persistence failed"):
        flow.create_standalone_component("Rollback me", actor=actor)

    assert flow.get_library_component("rollback_me", actor=actor) is None
    assert scope_repo.get_scope("component", "rollback_me") is None


def test_scope_persistence_failure_rolls_back_composition_creation() -> None:
    scope_repo = _MemoryScopeRepository(fail_on_set=True)
    flow = _build_flow(scope_repo)
    actor = _actor()

    with pytest.raises(RuntimeError, match="scope persistence failed"):
        flow.create_composition("rollback_plate", "Rollback dish", actor=actor)

    assert flow.get_library_composition("rollback_plate", actor=actor) is None
    assert scope_repo.scopes == {}


def test_scoped_component_recipe_creation_is_blocked_for_foreign_tenant() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=81, user_id=801)
    foreign = _actor(tenant_id=82, user_id=802)

    component = flow.create_standalone_component("Foreign recipe target", actor=owner)

    with pytest.raises(ValueError, match="component not found"):
        flow.create_component_recipe(
            component_id=component.component_id,
            recipe_name="Blocked recipe",
            yield_portions=4,
            actor=foreign,
        )

    _, recipes = flow.list_component_recipes(component_id=component.component_id, actor=owner)
    assert recipes == []


def test_scoped_recipe_ingredient_mutation_is_blocked_for_foreign_tenant() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=91, user_id=901)
    foreign = _actor(tenant_id=92, user_id=902)

    component = flow.create_standalone_component("Recipe parent", actor=owner)
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Owner recipe",
        yield_portions=4,
        actor=owner,
    )
    line = flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Salt",
        amount_value=10,
        amount_unit="g",
        actor=owner,
    )

    with pytest.raises(ValueError, match="component not found"):
        flow.update_recipe_ingredient_line(
            component_id=component.component_id,
            recipe_id=recipe.recipe_id,
            recipe_ingredient_line_id=line.recipe_ingredient_line_id,
            ingredient_name="Sea salt",
            amount_value=12,
            amount_unit="g",
            actor=foreign,
        )

    with pytest.raises(ValueError, match="component not found"):
        flow.delete_recipe_ingredient_line(
            component_id=component.component_id,
            recipe_id=recipe.recipe_id,
            recipe_ingredient_line_id=line.recipe_ingredient_line_id,
            actor=foreign,
        )

    detail_recipe, detail_lines = flow.get_component_recipe_detail(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        actor=owner,
    )
    assert detail_recipe.recipe_id == recipe.recipe_id
    assert [item.recipe_ingredient_line_id for item in detail_lines] == [line.recipe_ingredient_line_id]
    assert detail_lines[0].ingredient_name == "Salt"


def test_scoped_composition_mutation_is_blocked_for_foreign_tenant() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=101, user_id=1001)
    foreign = _actor(tenant_id=102, user_id=1002)

    composition = flow.create_composition("tenant-plate", "Tenant plate", actor=owner)
    component = flow.add_component_to_composition(
        composition_id=composition.composition_id,
        component_name="Fish",
        actor=owner,
    )

    with pytest.raises(ValueError, match="composition not found"):
        flow.remove_component_from_composition(
            composition_id=composition.composition_id,
            component_id=component.components[0].component_id,
            actor=foreign,
        )

    with pytest.raises(ValueError, match="composition not found"):
        flow.rename_component_in_composition(
            composition_id=composition.composition_id,
            component_id=component.components[0].component_id,
            new_component_name="Salmon",
            actor=foreign,
        )

    with pytest.raises(ValueError, match="component not found"):
        flow.reorder_components_in_composition(
            composition_id=composition.composition_id,
            ordered_entries=[(component.components[0].component_id, 0)],
            actor=foreign,
        )

    owner_view = flow.get_library_composition(composition.composition_id, actor=owner)
    assert owner_view is not None
    assert [item.component_id for item in owner_view.components] == [component.components[0].component_id]


def test_builder_api_persists_scopes_and_blocks_other_tenant_reads(tmp_path: Path) -> None:
    client, db_path = _sqlite_client(tmp_path)
    scope_repo = SQLiteBuilderObjectScopeRepository(db_path=db_path)
    tenant_one_headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-User-Id": "11"}
    tenant_two_headers = {"X-User-Role": "admin", "X-Tenant-Id": "2", "X-User-Id": "22"}

    component_rv = client.post(
        "/api/builder/components",
        json={"component_name": "Tenant One Soup"},
        headers=tenant_one_headers,
    )
    assert component_rv.status_code == 201
    component_id = str(((component_rv.get_json() or {}).get("component") or {}).get("component_id") or "")
    assert component_id

    composition_rv = client.post(
        "/api/builder/compositions",
        json={"composition_name": "Tenant One Dish"},
        headers=tenant_one_headers,
    )
    assert composition_rv.status_code == 201
    composition_id = str(((composition_rv.get_json() or {}).get("composition") or {}).get("composition_id") or "")
    assert composition_id

    component_scope = scope_repo.get_scope("component", component_id)
    composition_scope = scope_repo.get_scope("composition", composition_id)
    assert component_scope is not None
    assert composition_scope is not None
    assert component_scope.tenant_id == 1
    assert composition_scope.tenant_id == 1

    library_rv = client.get("/api/builder/library", headers=tenant_two_headers)
    assert library_rv.status_code == 200
    library_body = library_rv.get_json() or {}
    component_ids = {str(item.get("component_id") or "") for item in library_body.get("components") or []}
    composition_ids = {str(item.get("composition_id") or "") for item in library_body.get("compositions") or []}
    assert component_id not in component_ids
    assert composition_id not in composition_ids

    details_rv = client.get(f"/api/builder/components/{component_id}/details", headers=tenant_two_headers)
    assert details_rv.status_code == 400
    details_body = details_rv.get_json() or {}
    assert details_body.get("error") == "bad_request"


def test_import_endpoint_scopes_newly_created_objects(tmp_path: Path) -> None:
    client, db_path = _sqlite_client(tmp_path)
    scope_repo = SQLiteBuilderObjectScopeRepository(db_path=db_path)
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-User-Id": "11"}

    rv = client.post(
        "/api/builder/import",
        json={"lines": ["Pannbiff med potatis"]},
        headers=headers,
    )

    assert rv.status_code == 200
    body = rv.get_json() or {}
    assert body.get("ok") is True
    assert body.get("summary", {}).get("created_count") == 1

    tenant_records = scope_repo.list_for_tenant(1)
    assert any(record.object_type == "composition" for record in tenant_records)
    assert any(record.object_type == "component" for record in tenant_records)
    assert all(record.scope.tenant_id == 1 for record in tenant_records)


def test_builder_api_foreign_tenant_cannot_read_scoped_detail_paths(tmp_path: Path) -> None:
    client, db_path = _sqlite_client(tmp_path)
    scope_repo = SQLiteBuilderObjectScopeRepository(db_path=db_path)
    owner_headers = {"X-User-Role": "admin", "X-Tenant-Id": "1", "X-User-Id": "11"}
    foreign_headers = {"X-User-Role": "admin", "X-Tenant-Id": "2", "X-User-Id": "22"}

    component_rv = client.post(
        "/api/builder/components",
        json={"component_name": "API scoped component"},
        headers=owner_headers,
    )
    component_id = str(((component_rv.get_json() or {}).get("component") or {}).get("component_id") or "")
    recipe_rv = client.post(
        f"/api/builder/components/{component_id}/recipes",
        json={"recipe_name": "API recipe", "yield_portions": 4},
        headers=owner_headers,
    )
    recipe_id = str(((recipe_rv.get_json() or {}).get("recipe") or {}).get("recipe_id") or "")
    composition_rv = client.post(
        "/api/builder/compositions",
        json={"composition_name": "API scoped composition"},
        headers=owner_headers,
    )
    composition_id = str(((composition_rv.get_json() or {}).get("composition") or {}).get("composition_id") or "")

    assert scope_repo.get_scope("component", component_id) is not None
    assert scope_repo.get_scope("composition", composition_id) is not None

    assert client.get(f"/api/builder/components/{component_id}/recipes", headers=foreign_headers).status_code == 400
    assert client.get(
        f"/api/builder/components/{component_id}/recipes/{recipe_id}",
        headers=foreign_headers,
    ).status_code == 400
    assert client.get(
        f"/api/builder/components/{component_id}/declaration-readiness?include_declaration=1",
        headers=foreign_headers,
    ).status_code == 400
    assert client.get(
        f"/api/builder/compositions/{composition_id}/declaration-readiness?include_declaration=1",
        headers=foreign_headers,
    ).status_code == 400


def test_builder_api_foreign_tenant_rejection_leaves_composition_unchanged(tmp_path: Path) -> None:
    client, db_path = _sqlite_client(tmp_path)
    scope_repo = SQLiteBuilderObjectScopeRepository(db_path=db_path)
    owner_headers = {"X-User-Role": "admin", "X-Tenant-Id": "3", "X-User-Id": "33"}
    foreign_headers = {"X-User-Role": "admin", "X-Tenant-Id": "4", "X-User-Id": "44"}

    composition_rv = client.post(
        "/api/builder/compositions",
        json={"composition_name": "API tenant plate"},
        headers=owner_headers,
    )
    assert composition_rv.status_code == 201
    composition_id = str(((composition_rv.get_json() or {}).get("composition") or {}).get("composition_id") or "")

    component_rv = client.post(
        f"/api/builder/compositions/{composition_id}/components",
        json={"component_name": "API Fish", "role": "component"},
        headers=owner_headers,
    )
    assert component_rv.status_code == 200
    component_payload = (component_rv.get_json() or {}).get("composition") or {}
    initial_components = component_payload.get("components") or []
    component_id = next(
        (str(item.get("component_id") or "") for item in initial_components if item.get("component_name") == "API Fish"),
        "",
    )
    assert component_id
    initial_component_ids = {str(item.get("component_id") or "") for item in initial_components}

    rv = client.delete(
        f"/api/builder/compositions/{composition_id}/components/{component_id}",
        headers=foreign_headers,
    )

    assert rv.status_code == 400
    assert (rv.get_json() or {}).get("error") == "bad_request"

    owner_view = client.get("/api/builder/compositions", headers=owner_headers)
    assert owner_view.status_code == 200
    owner_body = owner_view.get_json() or {}
    target = next(
        (item for item in owner_body.get("compositions") or [] if item.get("composition_id") == composition_id),
        None,
    )
    assert target is not None
    components = target.get("components") or []
    assert {str(item.get("component_id") or "") for item in components} == initial_component_ids
    assert scope_repo.get_scope("composition", composition_id) is not None


def test_builder_api_foreign_tenant_cannot_attach_existing_component_to_composition(tmp_path: Path) -> None:
    client, db_path = _sqlite_client(tmp_path)
    scope_repo = SQLiteBuilderObjectScopeRepository(db_path=db_path)
    owner_headers = {"X-User-Role": "admin", "X-Tenant-Id": "5", "X-User-Id": "55"}
    foreign_headers = {"X-User-Role": "admin", "X-Tenant-Id": "6", "X-User-Id": "66"}

    component_rv = client.post(
        "/api/builder/components",
        json={"component_name": "Attach API Fish"},
        headers=owner_headers,
    )
    assert component_rv.status_code == 201
    component_id = str(((component_rv.get_json() or {}).get("component") or {}).get("component_id") or "")
    assert component_id

    composition_rv = client.post(
        "/api/builder/compositions",
        json={"composition_name": "Attach API Plate"},
        headers=foreign_headers,
    )
    assert composition_rv.status_code == 201
    composition_id = str(((composition_rv.get_json() or {}).get("composition") or {}).get("composition_id") or "")
    assert composition_id

    rv = client.post(
        f"/api/builder/compositions/{composition_id}/components/attach",
        json={"component_id": component_id},
        headers=owner_headers,
    )

    assert rv.status_code == 400
    assert (rv.get_json() or {}).get("error") == "bad_request"
    assert scope_repo.get_scope("composition", composition_id) is not None


def test_builder_api_foreign_tenant_cannot_render_composition_text(tmp_path: Path) -> None:
    client, db_path = _sqlite_client(tmp_path)
    scope_repo = SQLiteBuilderObjectScopeRepository(db_path=db_path)
    owner_headers = {"X-User-Role": "admin", "X-Tenant-Id": "7", "X-User-Id": "77"}
    foreign_headers = {"X-User-Role": "admin", "X-Tenant-Id": "8", "X-User-Id": "88"}

    composition_rv = client.post(
        "/api/builder/compositions",
        json={"composition_name": "Render API Plate"},
        headers=owner_headers,
    )
    assert composition_rv.status_code == 201
    composition_id = str(((composition_rv.get_json() or {}).get("composition") or {}).get("composition_id") or "")
    assert composition_id

    rv = client.get(
        f"/api/builder/compositions/{composition_id}/render/text",
        headers=foreign_headers,
    )

    assert rv.status_code == 400
    assert (rv.get_json() or {}).get("error") == "bad_request"
    assert scope_repo.get_scope("composition", composition_id) is not None
