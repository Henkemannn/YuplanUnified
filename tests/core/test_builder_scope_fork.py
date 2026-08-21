from __future__ import annotations

from pathlib import Path

import pytest

from core.app_factory import create_app
from core.builder import BuilderFlow
from core.builder.library_scope import ActorContext
from core.builder.library_scope import ObjectScope
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

    def get_scope(self, object_type: str, object_id: str) -> ObjectScope | None:
        return self.scopes.get((object_type, object_id))

    def set_scope(self, object_type: str, object_id: str, scope: ObjectScope) -> None:
        if self.fail_on_set:
            raise RuntimeError("scope persistence failed")
        self.scopes[(object_type, object_id)] = scope

    def delete_scope(self, object_type: str, object_id: str) -> None:
        self.scopes.pop((object_type, object_id), None)


def _actor(*, tenant_id: int = 1, user_id: int | None = 11, role: str = "cook") -> ActorContext:
    return ActorContext(tenant_id=tenant_id, user_id=user_id if user_id is not None else -1, site_id=None, role=role)


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
    db_path = tmp_path / "builder_scope_fork.db"
    app = create_app({"TESTING": True, "BUILDER_DB_PATH": str(db_path)})
    initialize_builder_sqlite(str(db_path))
    return app.test_client(), str(db_path)


def test_cook_can_read_and_fork_organisation_component() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    component = flow.create_standalone_component("Forkable soup", actor=editor)
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        yield_portions=4,
        actor=editor,
    )
    line = flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Salt",
        amount_value=10,
        amount_unit="g",
        actor=editor,
    )

    readable = flow.get_library_component(component.component_id, actor=cook)
    assert readable is not None

    forked = flow.fork_component(component.component_id, actor=cook)
    assert forked.component_id != component.component_id
    assert forked.canonical_name == component.canonical_name
    assert forked.categories == component.categories

    scope = scope_repo.get_scope("component", forked.component_id)
    assert scope == ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id=None,
        owner_user_id=20,
        visibility="private",
        source_object_id=component.component_id,
    )

    forked_recipe = flow.get_component_recipe_detail(component_id=forked.component_id, recipe_id=flow.list_component_recipes(component_id=forked.component_id, actor=cook)[1][0].recipe_id, actor=cook)
    assert forked_recipe[0].component_id == forked.component_id
    assert forked_recipe[1][0].ingredient_name == "Salt"
    assert forked_recipe[1][0].recipe_ingredient_line_id != line.recipe_ingredient_line_id

    owner_view = flow.get_library_component(component.component_id, actor=editor)
    assert owner_view is not None
    assert owner_view.canonical_name == component.canonical_name


def test_cook_cannot_directly_mutate_organisation_component() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    component = flow.create_standalone_component("Original soup", actor=editor)

    with pytest.raises(ValueError, match="component not found"):
        flow.rename_component(component.component_id, "Changed", actor=cook)

    with pytest.raises(ValueError, match="component not found"):
        flow.set_component_category(component.component_id, "side", actor=cook)

    with pytest.raises(ValueError, match="component not found"):
        flow.create_component_recipe(
            component_id=component.component_id,
            recipe_name="Blocked",
            yield_portions=2,
            actor=cook,
        )


def test_cook_private_fork_is_isolated_from_other_cook() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook_a = _actor(tenant_id=1, user_id=20, role="cook")
    cook_b = _actor(tenant_id=1, user_id=30, role="cook")

    component = flow.create_standalone_component("Isolation soup", actor=editor)
    forked = flow.fork_component(component.component_id, actor=cook_a)

    assert flow.get_library_component(forked.component_id, actor=cook_a) is not None
    assert flow.get_library_component(forked.component_id, actor=cook_b) is None

    with pytest.raises(ValueError, match="component not found"):
        flow.rename_component(forked.component_id, "Other", actor=cook_b)


def test_cook_missing_user_id_cannot_create_private_fork() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = ActorContext(tenant_id=1, user_id=None, site_id=None, role="cook")

    component = flow.create_standalone_component("No user soup", actor=editor)

    with pytest.raises(ValueError, match="actor.user_id is required"):
        flow.fork_component(component.component_id, actor=cook)


def test_cook_can_fork_and_edit_private_composition_shallowly() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    component = flow.create_standalone_component("Shared fish", actor=editor)
    composition = flow.create_composition("plate-shared", "Shared plate", actor=editor)
    flow.add_component_to_composition(
        composition_id=composition.composition_id,
        component_name=component.canonical_name,
        actor=editor,
    )

    forked_composition = flow.fork_composition(composition.composition_id, actor=cook)
    scope = scope_repo.get_scope("composition", forked_composition.composition_id)
    assert scope == ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id=None,
        owner_user_id=20,
        visibility="private",
        source_object_id=composition.composition_id,
    )

    assert len(forked_composition.components) == 1
    assert forked_composition.components[0].component_id == component.component_id

    forked_component = flow.fork_component(component.component_id, actor=cook)
    flow.remove_component_from_composition(
        composition_id=forked_composition.composition_id,
        component_id=component.component_id,
        actor=cook,
    )
    flow.attach_existing_component_to_composition(
        composition_id=forked_composition.composition_id,
        component_id=forked_component.component_id,
        actor=cook,
    )
    updated = flow.rename_component_in_composition(
        composition_id=forked_composition.composition_id,
        component_id=forked_component.component_id,
        new_component_name="Forked fish",
        actor=cook,
    )
    assert updated.components[0].component_id == forked_component.component_id
    assert updated.components[0].component_name == "Forked fish"
    assert flow.get_library_component(component.component_id, actor=editor) is not None
    assert flow.get_library_component(forked_component.component_id, actor=cook) is not None


def test_cook_resolve_composition_edit_target_reuses_private_fork() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook_a = _actor(tenant_id=1, user_id=20, role="cook")
    cook_b = _actor(tenant_id=1, user_id=30, role="cook")

    source = flow.create_composition("plate-edit-target", "Shared plate", actor=editor)
    flow.add_component_to_composition(
        composition_id=source.composition_id,
        component_name=flow.create_standalone_component("Edit target fish", actor=editor).canonical_name,
        actor=editor,
    )

    first = flow.resolve_composition_edit_target(source.composition_id, actor=cook_a)
    second = flow.resolve_composition_edit_target(source.composition_id, actor=cook_a)
    other = flow.resolve_composition_edit_target(source.composition_id, actor=cook_b)

    assert first.composition_id == second.composition_id
    assert first.composition_id != source.composition_id
    assert other.composition_id != first.composition_id

    first_scope = scope_repo.get_scope("composition", first.composition_id)
    assert first_scope == ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id=None,
        owner_user_id=20,
        visibility="private",
        source_object_id=source.composition_id,
    )
    other_scope = scope_repo.get_scope("composition", other.composition_id)
    assert other_scope == ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id=None,
        owner_user_id=30,
        visibility="private",
        source_object_id=source.composition_id,
    )

    assert flow.get_library_composition(first.composition_id, actor=cook_b) is None
    assert flow.get_library_composition(source.composition_id, actor=editor).composition_name == "Shared plate"


def test_cook_can_update_own_private_composition_but_not_shared_source() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    source = flow.create_composition("plate-update-target", "Shared plate", actor=editor)
    private_target = flow.resolve_composition_edit_target(source.composition_id, actor=cook)

    updated = flow.update_composition_metadata(
        private_target.composition_id,
        composition_name="Cook plate",
        library_group="fisk",
        actor=cook,
    )
    assert updated.composition_name == "Cook plate"
    assert updated.library_group == "fisk"
    assert flow.get_library_composition(source.composition_id, actor=editor).composition_name == "Shared plate"

    with pytest.raises(ValueError, match="composition not found"):
        flow.update_composition_metadata(
            source.composition_id,
            composition_name="Blocked",
            actor=cook,
        )

    assert flow.get_library_composition(private_target.composition_id, actor=cook).composition_name == "Cook plate"


def test_cook_b_cannot_read_or_reuse_cook_a_private_composition_fork() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook_a = _actor(tenant_id=1, user_id=20, role="cook")
    cook_b = _actor(tenant_id=1, user_id=30, role="cook")

    source = flow.create_composition("plate-private-visibility", "Private visibility plate", actor=editor)
    cook_a_target = flow.resolve_composition_edit_target(source.composition_id, actor=cook_a)
    cook_b_target = flow.resolve_composition_edit_target(source.composition_id, actor=cook_b)

    assert cook_a_target.composition_id != cook_b_target.composition_id
    assert flow.get_library_composition(cook_a_target.composition_id, actor=cook_b) is None
    assert flow.get_library_composition(cook_b_target.composition_id, actor=cook_a) is None


def test_cook_cannot_update_shared_composition_metadata_directly() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    source = flow.create_composition("plate-shared-block", "Shared blocked plate", actor=editor)

    with pytest.raises(ValueError, match="composition not found"):
        flow.update_composition_metadata(
            source.composition_id,
            composition_name="Blocked",
            actor=cook,
        )


def test_fork_scope_write_failure_rolls_back() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    component = flow.create_standalone_component("Rollback soup", actor=editor)

    scope_repo.fail_on_set = True

    with pytest.raises(RuntimeError, match="scope persistence failed"):
        flow.fork_component(component.component_id, actor=cook)

    assert flow.get_library_component("rollback_soup_2", actor=editor) is None
    assert scope_repo.get_scope("component", component.component_id) == ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )
    assert ("component", "rollback_soup_2") not in scope_repo.scopes


def test_component_details_persisted_on_fork_are_independent() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    component = flow.create_standalone_component("Detail soup", actor=editor)
    forked = flow.fork_component(component.component_id, actor=cook)
    assert forked.component_id != component.component_id
    assert scope_repo.get_scope("component", forked.component_id).source_object_id == component.component_id


def test_cook_can_read_private_fork_recipe_detail_scaling_and_traits() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook = _actor(tenant_id=1, user_id=20, role="cook")

    component = flow.create_standalone_component("Recipe read soup", actor=editor)
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        yield_portions=4,
        actor=editor,
    )
    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Salt",
        amount_value=10,
        amount_unit="g",
        trait_signals=["lactose"],
        actor=editor,
    )

    forked = flow.fork_component(component.component_id, actor=cook)
    _, forked_recipes = flow.list_component_recipes(component_id=forked.component_id, actor=cook)
    forked_recipe, forked_lines = flow.get_component_recipe_detail(
        component_id=forked.component_id,
        recipe_id=forked_recipes[0].recipe_id,
        actor=cook,
    )

    assert forked_recipe.component_id == forked.component_id
    assert forked_lines[0].ingredient_name == "Salt"

    scaling = flow.preview_component_recipe_scaling(
        component_id=forked.component_id,
        recipe_id=forked_recipe.recipe_id,
        target_portions=8,
        actor=cook,
    )
    traits = flow.preview_component_recipe_trait_signals(
        component_id=forked.component_id,
        recipe_id=forked_recipe.recipe_id,
        actor=cook,
    )

    assert scaling.component_id == forked.component_id
    assert traits.component_id == forked.component_id


def test_foreign_tenant_cannot_read_known_component_recipe_data() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    owner = _actor(tenant_id=1, user_id=10, role="editor")
    foreign = _actor(tenant_id=2, user_id=20, role="cook")

    component = flow.create_standalone_component("Foreign recipe soup", actor=owner)
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        yield_portions=4,
        actor=owner,
    )

    with pytest.raises(ValueError, match="component not found"):
        flow.get_component_recipe_detail(
            component_id=component.component_id,
            recipe_id=recipe.recipe_id,
            actor=foreign,
        )

    with pytest.raises(ValueError, match="component not found"):
        flow.preview_component_recipe_scaling(
            component_id=component.component_id,
            recipe_id=recipe.recipe_id,
            target_portions=8,
            actor=foreign,
        )

    with pytest.raises(ValueError, match="component not found"):
        flow.preview_component_recipe_trait_signals(
            component_id=component.component_id,
            recipe_id=recipe.recipe_id,
            actor=foreign,
        )


def test_private_fork_recipe_data_is_hidden_from_other_cook() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=10, role="editor")
    cook_a = _actor(tenant_id=1, user_id=20, role="cook")
    cook_b = _actor(tenant_id=1, user_id=30, role="cook")

    component = flow.create_standalone_component("Private recipe soup", actor=editor)
    flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        yield_portions=4,
        actor=editor,
    )

    forked = flow.fork_component(component.component_id, actor=cook_a)

    _, forked_recipes = flow.list_component_recipes(component_id=forked.component_id, actor=cook_a)
    with pytest.raises(ValueError, match="component not found"):
        flow.get_component_recipe_detail(
            component_id=forked.component_id,
            recipe_id=forked_recipes[0].recipe_id,
            actor=cook_b,
        )
