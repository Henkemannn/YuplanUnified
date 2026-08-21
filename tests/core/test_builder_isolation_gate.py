from __future__ import annotations

import pytest

from core.builder import BuilderFlow
from core.builder.library_scope import ActorContext
from core.builder.library_scope import ObjectScope
from core.builder.library_scope import can_read_object
from core.builder.library_scope import can_write_object
from core.components import ComponentService
from core.components import CompositionService
from core.components import InMemoryComponentAliasRepository
from core.components import InMemoryComponentRepository
from core.components import InMemoryCompositionRepository
from core.menu import InMemoryCompositionAliasRepository


class _MemoryScopeRepository:
    def __init__(self) -> None:
        self.scopes: dict[tuple[str, str], ObjectScope] = {}

    def get_scope(self, object_type: str, object_id: str) -> ObjectScope | None:
        return self.scopes.get((object_type, object_id))

    def find_private_fork_id(
        self,
        object_type: str,
        source_object_id: str,
        *,
        tenant_id: int,
        owner_user_id: int,
    ) -> str | None:
        for (stored_object_type, object_id), scope in reversed(list(self.scopes.items())):
            if (
                stored_object_type == object_type
                and scope.tenant_id == tenant_id
                and scope.owner_scope == "user"
                and scope.owner_user_id == owner_user_id
                and scope.visibility == "private"
                and scope.source_object_id == source_object_id
            ):
                return object_id
        return None

    def set_scope(self, object_type: str, object_id: str, scope: ObjectScope) -> None:
        self.scopes[(object_type, object_id)] = scope

    def delete_scope(self, object_type: str, object_id: str) -> None:
        self.scopes.pop((object_type, object_id), None)


def _actor(*, tenant_id: int, user_id: int, site_id: str | None, role: str) -> ActorContext:
    return ActorContext(tenant_id=tenant_id, user_id=user_id, site_id=site_id, role=role)


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


def test_isolation_gate_tenant_boundaries_block_foreign_lists_reads_and_mutations() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    tenant_a_editor = _actor(tenant_id=1, user_id=11, site_id="site-a", role="editor")
    tenant_a_cook = _actor(tenant_id=1, user_id=21, site_id="site-a", role="cook")
    tenant_b_cook = _actor(tenant_id=2, user_id=31, site_id="site-b", role="cook")

    component_a = flow.create_standalone_component("Tenant A Soup", actor=tenant_a_editor)
    composition_a = flow.create_composition("plate-a", "Tenant A Plate", actor=tenant_a_editor)
    flow.add_component_to_composition(
        composition_id=composition_a.composition_id,
        component_name=component_a.canonical_name,
        actor=tenant_a_editor,
    )

    component_b = flow.create_standalone_component("Tenant B Soup", actor=tenant_b_cook)
    composition_b = flow.create_composition("plate-b", "Tenant B Plate", actor=tenant_b_cook)

    assert component_a.component_id in {item.component_id for item in flow.list_library_components(actor=tenant_a_cook)}
    assert composition_a.composition_id in {item.composition_id for item in flow.list_library_compositions(actor=tenant_a_cook)}
    assert component_b.component_id not in {item.component_id for item in flow.list_library_components(actor=tenant_a_cook)}
    assert composition_b.composition_id not in {item.composition_id for item in flow.list_library_compositions(actor=tenant_a_cook)}
    assert flow.get_library_component(component_b.component_id, actor=tenant_a_cook) is None
    assert flow.get_library_composition(composition_b.composition_id, actor=tenant_a_cook) is None

    assert flow.list_library_components(actor=tenant_b_cook)
    assert flow.list_library_compositions(actor=tenant_b_cook)
    assert flow.get_library_component(component_a.component_id, actor=tenant_b_cook) is None
    assert flow.get_library_composition(composition_a.composition_id, actor=tenant_b_cook) is None

    for mutate in (
        lambda: flow.rename_component(component_b.component_id, "Tenant B Changed", actor=tenant_a_cook),
        lambda: flow.rename_component_in_composition(
            composition_id=composition_b.composition_id,
            component_id=component_b.component_id,
            new_component_name="Tenant B Changed",
            actor=tenant_a_cook,
        ),
    ):
        try:
            mutate()
        except ValueError as exc:
            assert "not found" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("foreign tenant mutation should fail")


def test_isolation_gate_private_owner_fork_preserves_source_and_blocks_other_cook() -> None:
    scope_repo = _MemoryScopeRepository()
    flow = _build_flow(scope_repo)
    editor = _actor(tenant_id=1, user_id=11, site_id="site-a", role="editor")
    cook_a = _actor(tenant_id=1, user_id=21, site_id="site-a", role="cook")
    cook_b = _actor(tenant_id=1, user_id=22, site_id="site-a", role="cook")

    source_component = flow.create_standalone_component("Cook Fork Soup", actor=editor)
    source_recipe = flow.create_component_recipe(
        component_id=source_component.component_id,
        recipe_name="Base",
        yield_portions=4,
        actor=editor,
    )
    flow.add_recipe_ingredient_line(
        component_id=source_component.component_id,
        recipe_id=source_recipe.recipe_id,
        ingredient_name="Salt",
        amount_value=10,
        amount_unit="g",
        actor=editor,
    )

    forked_component = flow.fork_component(source_component.component_id, actor=cook_a)
    fork_scope = scope_repo.get_scope("component", forked_component.component_id)
    assert fork_scope is not None
    assert fork_scope.visibility == "private"
    assert fork_scope.owner_user_id == cook_a.user_id
    assert fork_scope.source_object_id == source_component.component_id

    fork_recipe = flow.list_component_recipes(component_id=forked_component.component_id, actor=cook_a)[1][0]
    fork_recipe_detail = flow.get_component_recipe_detail(
        component_id=forked_component.component_id,
        recipe_id=fork_recipe.recipe_id,
        actor=cook_a,
    )
    assert fork_recipe_detail[0].component_id == forked_component.component_id
    assert fork_recipe_detail[1][0].ingredient_name == "Salt"

    updated_fork = flow.rename_component(forked_component.component_id, "Cook Fork Soup Updated", actor=cook_a)
    assert updated_fork.canonical_name == "Cook Fork Soup Updated"
    assert flow.get_library_component(source_component.component_id, actor=editor).canonical_name == "Cook Fork Soup"
    assert flow.get_library_component(forked_component.component_id, actor=cook_b) is None

    with pytest.raises(ValueError, match="component not found"):
        flow.rename_component(forked_component.component_id, "Blocked", actor=cook_b)

    with pytest.raises(ValueError, match="component not found"):
        flow.get_component_recipe_detail(
            component_id=forked_component.component_id,
            recipe_id=fork_recipe.recipe_id,
            actor=cook_b,
        )


def test_isolation_gate_site_scope_matches_current_read_write_contract() -> None:
    same_site = _actor(tenant_id=1, user_id=21, site_id="site-a", role="cook")
    other_site = _actor(tenant_id=1, user_id=22, site_id="site-b", role="cook")
    site_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=99,
        visibility="site",
        source_object_id=None,
    )

    assert can_read_object(same_site, site_scope) is True
    assert can_write_object(same_site, site_scope) is False
    assert can_read_object(other_site, site_scope) is False
    assert can_write_object(other_site, site_scope) is False


def test_isolation_gate_shared_admin_path_still_works_with_scope_enforcement() -> None:
    flow = _build_flow(_MemoryScopeRepository())
    admin = _actor(tenant_id=1, user_id=11, site_id="site-a", role="admin")

    component = flow.create_standalone_component("Shared Soup", actor=admin)
    composition = flow.create_composition("plate-shared", "Shared Plate", actor=admin)
    flow.add_component_to_composition(
        composition_id=composition.composition_id,
        component_name=component.canonical_name,
        actor=admin,
    )

    assert flow.get_library_component(component.component_id, actor=admin) is not None
    assert flow.get_library_composition(composition.composition_id, actor=admin) is not None
    assert component.component_id in {item.component_id for item in flow.list_library_components(actor=admin)}
    assert composition.composition_id in {item.composition_id for item in flow.list_library_compositions(actor=admin)}
