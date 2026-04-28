from __future__ import annotations

import pytest

from core.builder import BuilderFlow
from core.components import (
    ComponentService,
    InMemoryComponentRepository,
    CompositionService,
    InMemoryCompositionRepository,
)
from core.menu import (
    InMemoryCompositionAliasRepository,
    create_composition_alias,
)


def _build_flow() -> BuilderFlow:
    component_repository = InMemoryComponentRepository()
    composition_repository = InMemoryCompositionRepository()
    alias_repository = InMemoryCompositionAliasRepository()

    component_service = ComponentService(repository=component_repository)
    composition_service = CompositionService(repository=composition_repository)

    return BuilderFlow(
        component_service=component_service,
        composition_service=composition_service,
        composition_repository=composition_repository,
        alias_repository=alias_repository,
    )


def test_create_composition_and_add_components_through_builder_flow() -> None:
    flow = _build_flow()

    flow.create_composition(composition_id="plate", composition_name="Plate")
    updated = flow.add_component_to_composition(
        composition_id="plate",
        component_name="Main component",
        role="main",
    )

    assert updated.composition_id == "plate"
    assert len(updated.components) == 1
    assert updated.components[0].component_id == "main_component"


def test_create_composition_with_generated_id_without_menu_context() -> None:
    flow = _build_flow()

    created = flow.create_composition_with_generated_id(composition_name="Free Dish")

    assert created.composition_name == "Free Dish"
    assert created.composition_id.startswith("cmp_")
    assert len(created.composition_id) == 10
    assert created.components == []


def test_free_create_seeded_composition_from_name_creates_component_links_and_entities() -> None:
    flow = _build_flow()

    created = flow.create_composition_with_generated_id(
        composition_name="Pannbiff med rastrekt potatis och loksas",
        seed_components=True,
    )

    assert len(created.components) == 3
    assert [item.component_name for item in created.components] == [
        "Pannbiff",
        "Rastrekt potatis",
        "Loksas",
    ]
    library_components = {item.component_id for item in flow.list_library_components()}
    assert all(link.component_id in library_components for link in created.components)


def test_free_create_seeded_composition_reuses_existing_component_entities() -> None:
    flow = _build_flow()
    existing = flow.create_standalone_component("Pannbiff")

    created = flow.create_composition_with_generated_id(
        composition_name="Pannbiff med potatis",
        seed_components=True,
    )

    assert created.components[0].component_id == existing.component_id
    assert len([item for item in flow.list_library_components() if item.component_id == existing.component_id]) == 1


def test_free_create_empty_shell_only_when_seeding_disabled() -> None:
    flow = _build_flow()

    seeded = flow.create_composition_with_generated_id(
        composition_name="Fisk med potatis",
        seed_components=True,
    )
    shell = flow.create_composition_with_generated_id(
        composition_name="Fisk med potatis",
        seed_components=False,
    )

    assert len(seeded.components) > 0
    assert shell.components == []


def test_create_standalone_component_without_menu_or_composition_context() -> None:
    flow = _build_flow()

    created = flow.create_standalone_component("Mashed Potatoes")

    assert created.component_id == "mashed_potatoes"
    assert created.canonical_name == "Mashed Potatoes"
    assert flow.list_compositions() == []


def test_create_standalone_component_rejects_empty_name() -> None:
    flow = _build_flow()

    with pytest.raises(ValueError, match="component_name must be non-empty"):
        flow.create_standalone_component("   ")


def test_attach_existing_component_to_composition_reuses_component_id_without_dup_entity() -> None:
    flow = _build_flow()
    created_component = flow.create_standalone_component("Mashed Potatoes")
    flow.create_composition(composition_id="plate", composition_name="Plate")

    updated = flow.attach_existing_component_to_composition(
        composition_id="plate",
        component_id=created_component.component_id,
        role="component",
    )

    assert len(updated.components) == 1
    assert updated.components[0].component_id == created_component.component_id
    assert updated.components[0].component_name == "Mashed Potatoes"
    listed = flow.list_library_components()
    assert len([item for item in listed if item.component_id == created_component.component_id]) == 1


def test_attach_existing_component_rejects_invalid_or_empty_ids() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")

    with pytest.raises(ValueError, match="component_id must be non-empty"):
        flow.attach_existing_component_to_composition(composition_id="plate", component_id="   ")

    with pytest.raises(ValueError, match="component not found"):
        flow.attach_existing_component_to_composition(composition_id="plate", component_id="unknown")


def test_attach_existing_component_is_library_only_and_has_no_menu_linkage_requirement() -> None:
    flow = _build_flow()
    created_component = flow.create_standalone_component("Sauce")
    created_composition = flow.create_composition_with_generated_id(composition_name="Fish")

    updated = flow.attach_existing_component_to_composition(
        composition_id=created_composition.composition_id,
        component_id=created_component.component_id,
        role="component",
    )

    assert updated.composition_id == created_composition.composition_id
    assert [item.component_id for item in updated.components] == [created_component.component_id]


def test_attach_existing_component_duplicate_behavior_is_deterministic() -> None:
    flow = _build_flow()
    created_component = flow.create_standalone_component("Rice")
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.attach_existing_component_to_composition(
        composition_id="plate",
        component_id=created_component.component_id,
        role="component",
    )

    with pytest.raises(ValueError, match="component already exists in composition"):
        flow.attach_existing_component_to_composition(
            composition_id="plate",
            component_id=created_component.component_id,
            role="component",
        )


def test_library_listing_returns_separate_sorted_components_and_compositions() -> None:
    flow = _build_flow()
    flow.create_standalone_component("zeta")
    flow.create_standalone_component("Alpha")
    flow.create_composition_with_generated_id(composition_name="Zulu dish")
    flow.create_composition_with_generated_id(composition_name="alpha dish")

    components = flow.list_library_components()
    compositions = flow.list_library_compositions()

    assert [item.canonical_name for item in components] == ["Alpha", "zeta"]
    assert [item.composition_name for item in compositions] == ["alpha dish", "Zulu dish"]


def test_library_listing_includes_standalone_created_entities_without_menu_linkage() -> None:
    flow = _build_flow()
    created_component = flow.create_standalone_component("Mashed Potatoes")
    created_composition = flow.create_composition_with_generated_id(composition_name="Fish Soup")

    components = flow.list_library_components()
    compositions = flow.list_library_compositions()

    assert any(item.component_id == created_component.component_id for item in components)
    assert any(item.composition_id == created_composition.composition_id for item in compositions)


def test_library_listing_does_not_generate_new_composition_ids() -> None:
    flow = _build_flow()
    created_composition = flow.create_composition_with_generated_id(composition_name="Open me")
    before_ids = {item.composition_id for item in flow.list_compositions()}

    listed = flow.list_library_compositions()
    after_ids = {item.composition_id for item in flow.list_compositions()}

    assert created_composition.composition_id in {item.composition_id for item in listed}
    assert after_ids == before_ids


def test_library_import_creates_compositions_without_menu_context() -> None:
    flow = _build_flow()

    summary = flow.import_library_text_lines(["Kottbullar med potatismos", "Fiskgratang"])

    assert summary.imported_count == 2
    assert summary.created_count == 2
    assert summary.reused_count == 0
    assert len(summary.row_results) == 2
    assert len(flow.list_compositions()) == 2
    assert not hasattr(flow, "_menu_service")


def test_library_import_suggests_components_and_learns_alias() -> None:
    flow = _build_flow()

    summary = flow.import_library_text_lines(["Kottbullar med graddsas och rodbetor"])

    assert summary.created_count == 1
    created_id = summary.row_results[0].composition_id
    created = flow._composition_repository.get(created_id)
    assert created is not None
    component_names = [item.component_name for item in created.components]
    assert component_names == ["Kottbullar", "Graddsas", "Rodbetor"]
    aliases = flow._alias_repository.find_by_alias_norm("kottbullar graddsas rodbetor")
    assert len(aliases) == 1
    assert aliases[0].composition_id == created_id


def test_library_import_persists_component_entities_and_links_to_composition() -> None:
    flow = _build_flow()

    summary = flow.import_library_text_lines(["Kottbullar med potatismos"])
    created_id = summary.row_results[0].composition_id
    created = flow._composition_repository.get(created_id)

    assert created is not None
    assert len(created.components) == 2

    library_components = {item.component_id: item for item in flow.list_library_components()}
    for linked in created.components:
        assert linked.component_id in library_components
        assert library_components[linked.component_id].canonical_name == linked.component_name


def test_library_import_reuses_existing_component_entity_when_names_match() -> None:
    flow = _build_flow()
    existing = flow.create_standalone_component("Kottbullar")

    summary = flow.import_library_text_lines(["Kottbullar med rodbetor"])
    created = flow._composition_repository.get(summary.row_results[0].composition_id)

    assert created is not None
    assert created.components[0].component_id == existing.component_id
    all_components = [item for item in flow.list_library_components() if item.component_id == existing.component_id]
    assert len(all_components) == 1


def test_library_import_does_not_duplicate_component_entities_across_compositions() -> None:
    flow = _build_flow()

    flow.import_library_text_lines(["Kottbullar med potatismos"])
    flow.import_library_text_lines(["Kottbullar med graddsas"])

    kottbullar = [
        item
        for item in flow.list_library_components()
        if item.canonical_name.lower() == "kottbullar"
    ]
    assert len(kottbullar) == 1


def test_library_import_deterministic_breakdown_does_not_leave_empty_composition() -> None:
    flow = _build_flow()

    summary = flow.import_library_text_lines(["Fisk med potatis"])
    created = flow._composition_repository.get(summary.row_results[0].composition_id)

    assert created is not None
    assert len(created.components) > 0


def test_library_import_reuses_existing_alias_and_requires_no_day_or_meal() -> None:
    flow = _build_flow()
    first = flow.import_library_text_lines(["No Match"])

    second = flow.import_library_text_lines(["No Match"])

    assert first.created_count == 1
    assert second.created_count == 0
    assert second.reused_count == 1
    assert second.row_results[0].composition_id == first.row_results[0].composition_id


def test_library_import_rejects_empty_input_lines() -> None:
    flow = _build_flow()

    with pytest.raises(ValueError, match="lines must contain at least one non-empty text"):
        flow.import_library_text_lines(["   ", ""])


def test_component_alias_reused_when_attaching_to_composition() -> None:
    flow = _build_flow()
    existing = flow.create_standalone_component("Kokt potatis")
    flow.add_component_alias(component_id=existing.component_id, alias_text="potatis kokt")
    flow.create_composition(composition_id="plate", composition_name="Plate")

    updated = flow.add_component_to_composition(
        composition_id="plate",
        component_name="potatis kokt",
        role="component",
    )

    assert updated.components[0].component_id == existing.component_id
    names = [item.canonical_name for item in flow.list_library_components()]
    assert names.count("Kokt potatis") == 1


def test_component_no_match_creates_new_component() -> None:
    flow = _build_flow()
    flow.create_standalone_component("Kokt potatis")

    created = flow.create_standalone_component("Stekt fisk")

    assert created.canonical_name == "Stekt fisk"
    names = [item.canonical_name for item in flow.list_library_components()]
    assert "Kokt potatis" in names
    assert "Stekt fisk" in names


def test_repeated_component_import_reuses_existing_component() -> None:
    flow = _build_flow()

    first = flow.import_library_text_lines(["Kottbullar med potatis"])
    second = flow.import_library_text_lines(["Kottbullar med sas"])

    assert first.created_count == 1
    assert second.created_count == 1
    kottbullar = [
        item
        for item in flow.list_library_components()
        if item.canonical_name.lower() == "kottbullar"
    ]
    assert len(kottbullar) == 1


def test_uncertain_component_matches_are_reported_but_import_continues() -> None:
    flow = _build_flow()
    flow.create_standalone_component("Kokt potatis")

    summary = flow.import_library_text_lines(["Kokt potatisar"])

    assert summary.imported_count == 1
    assert summary.created_count == 1
    assert summary.reused_count == 0
    assert len(summary.component_review_items) == 1
    review = summary.component_review_items[0]
    assert review.get("status") == "possible_match"
    possible = review.get("possible_matches") or []
    assert possible[0].get("component_name") == "Kokt potatis"


def test_remove_component_from_composition_through_builder_flow() -> None:
    flow = _build_flow()

    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="component",
    )
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Potatoes",
        role="component",
    )

    updated = flow.remove_component_from_composition(
        composition_id="plate",
        component_id="fish",
    )

    assert [item.component_id for item in updated.components] == ["potatoes"]


def test_rename_component_in_composition_through_builder_flow() -> None:
    flow = _build_flow()

    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="connector",
    )
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Potatoes",
        role="component",
    )

    updated = flow.rename_component_in_composition(
        composition_id="plate",
        component_id="fish",
        new_component_name="Salmon",
    )

    component_ids = [item.component_id for item in updated.components]
    assert component_ids == ["salmon", "potatoes"]
    assert updated.components[0].role == "connector"
    assert updated.components[0].sort_order == 10


def test_rename_component_in_composition_rejects_empty_name() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="component",
    )

    with pytest.raises(ValueError, match="component_name must be non-empty"):
        flow.rename_component_in_composition(
            composition_id="plate",
            component_id="fish",
            new_component_name="   ",
        )


def test_update_component_role_in_composition_through_builder_flow() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="component",
    )

    updated = flow.update_component_role_in_composition(
        composition_id="plate",
        component_id="fish",
        role="main protein",
    )

    assert len(updated.components) == 1
    assert updated.components[0].component_id == "fish"
    assert updated.components[0].role == "main protein"


def test_swedish_suggestions_preserve_display_names_and_normalize_ids() -> None:
    flow = _build_flow()
    raw_text = "Köttbullar med gräddsås och rödbetor"

    display_names = flow._suggest_components_from_unresolved_text(raw_text)
    assert display_names == ["Köttbullar", "Gräddsås", "Rödbetor"]

    summary = flow.import_library_text_lines([raw_text])
    created_id = summary.row_results[0].composition_id
    created = flow._composition_repository.get(created_id)
    assert created is not None

    component_ids = [item.component_id for item in created.components]
    assert component_ids == ["kottbullar", "graddsas", "rodbetor"]
    component_names = [item.component_name for item in created.components]
    assert component_names == ["Köttbullar", "Gräddsås", "Rödbetor"]


def test_conflicting_alias_norm_does_not_overwrite_existing_mapping() -> None:
    flow = _build_flow()
    existing = flow.create_composition(composition_id="plate_existing", composition_name="Existing")
    create_composition_alias(
        alias_repository=flow._alias_repository,
        alias_id="a-existing",
        composition_id=existing.composition_id,
        alias_text="No Match",
        composition_repository=flow._composition_repository,
        source="manual",
        confidence=1.0,
    )

    new_comp = flow.create_composition(composition_id="plate_new", composition_name="New")

    warning = flow._create_manual_alias_for_composition(
        composition_id=new_comp.composition_id,
        unresolved_text="No Match",
    )

    same_norm_aliases = flow._alias_repository.find_by_alias_norm("no match")
    assert len(same_norm_aliases) == 1
    assert same_norm_aliases[0].composition_id == "plate_existing"
    assert warning is not None


def test_rename_component_in_composition_updates_component_name() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fisk",
        role="component",
    )

    updated = flow.rename_component_in_composition(
        composition_id="plate",
        component_id="fisk",
        new_component_name="Köttbullar",
    )

    assert len(updated.components) == 1
    assert updated.components[0].component_name == "Köttbullar"
    assert updated.components[0].component_id == "kottbullar"


def test_rename_component_in_composition_removes_old_coarse_component_from_library() -> None:
    """After renaming a coarse component, the old entity must no longer appear in list_library_components."""
    flow = _build_flow()
    flow.create_composition(composition_id="dish1", composition_name="Pannbiff")
    flow.add_component_to_composition(
        composition_id="dish1",
        component_name="Stekt lök, potatis",
        role="component",
    )

    old_ids = {item.component_id for item in flow.list_library_components()}
    assert "stekt_lok_potatis" in old_ids

    flow.rename_component_in_composition(
        composition_id="dish1",
        component_id="stekt_lok_potatis",
        new_component_name="Stekt lök",
    )
    flow.add_component_to_composition(
        composition_id="dish1",
        component_name="Kokt potatis",
        role="component",
    )

    library_ids = {item.component_id for item in flow.list_library_components()}
    assert "stekt_lok_potatis" not in library_ids, "Old coarse component must be purged from library after rename"
    assert "stekt_lok" in library_ids
    assert "kokt_potatis" in library_ids


def test_rename_component_in_composition_keeps_old_component_when_still_referenced_elsewhere() -> None:
    """Old component entity must NOT be deleted if it is still linked to another composition."""
    flow = _build_flow()
    flow.create_composition(composition_id="dish1", composition_name="Dish 1")
    flow.create_composition(composition_id="dish2", composition_name="Dish 2")
    flow.add_component_to_composition(
        composition_id="dish1",
        component_name="Fish",
        role="component",
    )
    # Attach the same component entity to dish2
    flow.attach_existing_component_to_composition(
        composition_id="dish2",
        component_id="fish",
        role="component",
    )

    # Rename fish out of dish1 only
    flow.rename_component_in_composition(
        composition_id="dish1",
        component_id="fish",
        new_component_name="Salmon",
    )

    library_ids = {item.component_id for item in flow.list_library_components()}
    # "fish" must still be in the library because dish2 still references it
    assert "fish" in library_ids
    assert "salmon" in library_ids


def test_builder_flow_component_recipe_structured_ingredient_storage() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Meatballs")

    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="site",
        yield_portions=20,
        is_primary=True,
    )
    line = flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Potato",
        amount_value=900,
        amount_unit="g",
        note="peeled",
        sort_order=10,
    )
    fetched_recipe, lines = flow.get_component_recipe_detail(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
    )

    assert fetched_recipe.yield_portions == 20
    assert line.quantity_value == 900
    assert line.quantity_unit == "g"
    assert len(lines) == 1
    assert lines[0].ingredient_name == "Potato"
    assert lines[0].note == "peeled"
    updated_component = flow.list_library_components()[0]
    assert updated_component.primary_recipe_id == recipe.recipe_id


def test_builder_flow_recipe_must_belong_to_component() -> None:
    flow = _build_flow()
    first = flow.create_standalone_component("Fish")
    second = flow.create_standalone_component("Potato")
    recipe = flow.create_component_recipe(
        component_id=first.component_id,
        recipe_name="Fish Base",
        visibility="private",
        yield_portions=10,
    )

    with pytest.raises(ValueError, match="does not belong to component"):
        flow.add_recipe_ingredient_line(
            component_id=second.component_id,
            recipe_id=recipe.recipe_id,
            ingredient_name="Salt",
            amount_value=1,
            amount_unit="g",
        )


def test_builder_flow_lists_component_recipes_primary_first_then_name() -> None:
    flow = _build_flow()
    first = flow.create_standalone_component("Fish")
    second = flow.create_standalone_component("Potato")

    r_b = flow.create_component_recipe(
        component_id=first.component_id,
        recipe_name="B Recipe",
        visibility="private",
        yield_portions=10,
    )
    flow.create_component_recipe(
        component_id=first.component_id,
        recipe_name="A Recipe",
        visibility="private",
        yield_portions=10,
    )
    flow.create_component_recipe(
        component_id=second.component_id,
        recipe_name="Other",
        visibility="private",
        yield_portions=10,
    )
    flow.set_component_primary_recipe(component_id=first.component_id, recipe_id=r_b.recipe_id)

    component, recipes = flow.list_component_recipes(component_id=first.component_id)

    assert component.component_id == first.component_id
    assert [item.recipe_name for item in recipes] == ["B Recipe", "A Recipe"]


def test_builder_flow_updates_recipe_metadata() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Fish")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Old",
        visibility="private",
        yield_portions=10,
        notes="old",
    )

    updated = flow.update_component_recipe_metadata(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        recipe_name="New",
        yield_portions=24,
        visibility="site",
        notes="new",
    )

    assert updated.recipe_name == "New"
    assert updated.yield_portions == 24
    assert updated.visibility == "site"
    assert updated.notes == "new"


def test_builder_flow_updates_and_deletes_recipe_ingredient_line() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Soup")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="private",
        yield_portions=12,
    )
    line = flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Salt",
        amount_value=10,
        amount_unit="g",
        note="initial",
        sort_order=10,
    )

    updated = flow.update_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        recipe_ingredient_line_id=line.recipe_ingredient_line_id,
        ingredient_name="Sea salt",
        amount_value=12,
        amount_unit="g",
        note="updated",
        sort_order=20,
    )
    assert updated.ingredient_name == "Sea salt"
    assert str(updated.quantity_value) == "12"
    assert updated.note == "updated"
    assert updated.sort_order == 20

    flow.delete_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        recipe_ingredient_line_id=line.recipe_ingredient_line_id,
    )
    _, lines = flow.get_component_recipe_detail(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
    )
    assert lines == []


def test_builder_flow_recipe_delete_guard_and_delete_after_unset_primary() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Stew")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="private",
        yield_portions=8,
        is_primary=True,
    )

    with pytest.raises(ValueError, match="cannot delete primary recipe"):
        flow.delete_component_recipe(component_id=component.component_id, recipe_id=recipe.recipe_id)

    flow.set_component_primary_recipe(component_id=component.component_id, recipe_id=None)
    flow.delete_component_recipe(component_id=component.component_id, recipe_id=recipe.recipe_id)

    _, recipes = flow.list_component_recipes(component_id=component.component_id)
    assert recipes == []


def test_builder_flow_recipe_scaling_preview_scales_amounts_deterministically() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Soup")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="private",
        yield_portions=4,
    )
    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Water",
        amount_value=2,
        amount_unit="l",
        note="cold",
        sort_order=10,
    )
    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Salt",
        amount_value=8,
        amount_unit="g",
        note=None,
        sort_order=20,
    )

    preview = flow.preview_component_recipe_scaling(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        target_portions=10,
    )

    assert preview.source_yield_portions == 4
    assert preview.target_portions == 10
    assert str(preview.scaling_factor) == "2.5"
    assert [line.ingredient_name for line in preview.ingredient_lines] == ["Water", "Salt"]
    assert [str(line.original_amount_value) for line in preview.ingredient_lines] == ["2", "8"]
    assert [str(line.scaled_amount_value) for line in preview.ingredient_lines] == ["5.0", "20.0"]
    assert [line.amount_unit for line in preview.ingredient_lines] == ["l", "g"]
    assert [line.note for line in preview.ingredient_lines] == ["cold", None]


def test_builder_flow_recipe_scaling_preview_rejects_invalid_target_portions() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Soup")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="private",
        yield_portions=4,
    )

    with pytest.raises(ValueError, match="target_portions must be > 0"):
        flow.preview_component_recipe_scaling(
            component_id=component.component_id,
            recipe_id=recipe.recipe_id,
            target_portions=0,
        )


def test_builder_flow_recipe_scaling_preview_enforces_component_ownership() -> None:
    flow = _build_flow()
    c1 = flow.create_standalone_component("Fish")
    c2 = flow.create_standalone_component("Potato")
    recipe = flow.create_component_recipe(
        component_id=c1.component_id,
        recipe_name="Fish Base",
        visibility="private",
        yield_portions=6,
    )

    with pytest.raises(ValueError, match="does not belong to component"):
        flow.preview_component_recipe_scaling(
            component_id=c2.component_id,
            recipe_id=recipe.recipe_id,
            target_portions=12,
        )


def test_builder_flow_recipe_ingredient_line_persists_trait_signals() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Sauce")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="private",
        yield_portions=8,
    )

    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Cream",
        amount_value=2,
        amount_unit="dl",
        trait_signals=["lactose", "  lactose  ", "fish"],
    )
    _, lines = flow.get_component_recipe_detail(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
    )

    assert len(lines) == 1
    assert lines[0].trait_signals == ("fish", "lactose")


def test_builder_flow_recipe_trait_preview_exposes_union_and_line_signals() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Fish Soup")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="private",
        yield_portions=8,
    )
    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Cream",
        amount_value=2,
        amount_unit="dl",
        trait_signals=["lactose"],
        sort_order=10,
    )
    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Cod",
        amount_value=500,
        amount_unit="g",
        trait_signals=["fish"],
        sort_order=20,
    )

    preview = flow.preview_component_recipe_trait_signals(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
    )

    assert preview.recipe_name == "Base"
    assert preview.trait_signals_present == ("fish", "lactose")
    assert [line.ingredient_name for line in preview.ingredient_lines] == ["Cream", "Cod"]
    assert [line.trait_signals for line in preview.ingredient_lines] == [("lactose",), ("fish",)]


def test_builder_flow_recipe_trait_preview_enforces_component_ownership() -> None:
    flow = _build_flow()
    c1 = flow.create_standalone_component("Fish")
    c2 = flow.create_standalone_component("Potato")
    recipe = flow.create_component_recipe(
        component_id=c1.component_id,
        recipe_name="Fish Base",
        visibility="private",
        yield_portions=6,
    )

    with pytest.raises(ValueError, match="does not belong to component"):
        flow.preview_component_recipe_trait_signals(
            component_id=c2.component_id,
            recipe_id=recipe.recipe_id,
        )


def test_component_declaration_readiness_aggregates_primary_recipe_trait_sources() -> None:
    flow = _build_flow()
    component = flow.create_standalone_component("Fish Sauce")
    recipe = flow.create_component_recipe(
        component_id=component.component_id,
        recipe_name="Base",
        visibility="private",
        yield_portions=10,
    )
    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Cod",
        amount_value=500,
        amount_unit="g",
        trait_signals=["fish"],
        sort_order=10,
    )
    flow.add_recipe_ingredient_line(
        component_id=component.component_id,
        recipe_id=recipe.recipe_id,
        ingredient_name="Cream",
        amount_value=2,
        amount_unit="dl",
        trait_signals=["lactose"],
        sort_order=20,
    )

    readiness = flow.preview_component_declaration_readiness(component_id=component.component_id)

    assert readiness.component_id == component.component_id
    assert readiness.primary_recipe_id is None
    assert readiness.trait_signals_present == ("fish", "lactose")
    assert readiness.conflict_preview.conflicts_present == ("fish_relevant", "lactose_relevant")
    assert [source.conflict_key for source in readiness.conflict_preview.conflict_sources] == [
        "fish_relevant",
        "lactose_relevant",
    ]
    assert [source.ingredient_name for source in readiness.ingredient_sources] == ["Cod", "Cream"]
    assert any("missing primary recipe" in message for message in readiness.warnings)


def test_composition_declaration_readiness_aggregates_component_signals_deterministically() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate_1", composition_name="Fish Plate")

    added = flow.add_component_to_composition(
        composition_id="plate_1",
        component_name="Sauce",
        role="sauce",
    )
    sauce_component_id = added.components[0].component_id

    added = flow.add_component_to_composition(
        composition_id="plate_1",
        component_name="Fish",
        role="main",
    )
    fish_component_id = next(
        item.component_id for item in added.components if item.component_name == "Fish"
    )

    fish_recipe = flow.create_component_recipe(
        component_id=fish_component_id,
        recipe_name="Fish Base",
        visibility="private",
        yield_portions=10,
    )
    flow.add_recipe_ingredient_line(
        component_id=fish_component_id,
        recipe_id=fish_recipe.recipe_id,
        ingredient_name="Cod",
        amount_value=400,
        amount_unit="g",
        trait_signals=["fish"],
        sort_order=10,
    )

    sauce_recipe = flow.create_component_recipe(
        component_id=sauce_component_id,
        recipe_name="Sauce Base",
        visibility="private",
        yield_portions=10,
    )
    flow.add_recipe_ingredient_line(
        component_id=sauce_component_id,
        recipe_id=sauce_recipe.recipe_id,
        ingredient_name="Cream",
        amount_value=3,
        amount_unit="dl",
        trait_signals=["lactose"],
        sort_order=10,
    )

    readiness = flow.preview_composition_declaration_readiness(composition_id="plate_1")

    assert readiness.composition_id == "plate_1"
    assert readiness.trait_signals_present == ("fish", "lactose")
    assert readiness.conflict_preview.conflicts_present == ("fish_relevant", "lactose_relevant")
    assert [component.component_name for component in readiness.components] == ["Sauce", "Fish"]
    assert [component.trait_signals_present for component in readiness.components] == [
        ("lactose",),
        ("fish",),
    ]
    assert any("missing primary recipe" in message for message in readiness.warnings)


def test_reorder_components_in_composition_persists_explicit_sort_order() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    first = flow.add_component_to_composition(
        composition_id="plate",
        component_name="Potato",
        role="side",
    )
    second = flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="main",
    )

    original = second.components
    reordered = flow.reorder_components_in_composition(
        composition_id="plate",
        ordered_entries=[
            (original[1].component_id, original[1].sort_order),
            (original[0].component_id, original[0].sort_order),
        ],
    )

    assert [item.component_name for item in reordered.components] == ["Fish", "Potato"]
    assert [item.sort_order for item in reordered.components] == [10, 20]


def test_reorder_components_order_is_deterministic_after_reload_for_text_outputs() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(composition_id="plate", component_name="A")
    flow.add_component_to_composition(composition_id="plate", component_name="B")
    added = flow.add_component_to_composition(composition_id="plate", component_name="C")

    reordered = flow.reorder_components_in_composition(
        composition_id="plate",
        ordered_entries=[
            (added.components[2].component_id, added.components[2].sort_order),
            (added.components[0].component_id, added.components[0].sort_order),
            (added.components[1].component_id, added.components[1].sort_order),
        ],
    )

    reloaded = flow.list_compositions()
    plate = next(item for item in reloaded if item.composition_id == "plate")
    assert [item.component_name for item in plate.components] == ["C", "A", "B"]
    assert [item.sort_order for item in plate.components] == [10, 20, 30]
    assert [item.component_name for item in reordered.components] == ["C", "A", "B"]


def test_render_composition_text_model_follows_persisted_sort_order() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(composition_id="plate", component_name="Potato", role="side")
    with_two = flow.add_component_to_composition(
        composition_id="plate",
        component_name="Fish",
        role="main",
    )

    flow.reorder_components_in_composition(
        composition_id="plate",
        ordered_entries=[
            (with_two.components[1].component_id, with_two.components[1].sort_order),
            (with_two.components[0].component_id, with_two.components[0].sort_order),
        ],
    )

    rendered = flow.render_composition_text_model(composition_id="plate")
    assert rendered.text == "Plate: Fish (main), Potato (side)"
    assert [item.component_name for item in rendered.rendered_components] == ["Fish", "Potato"]
    assert [item.sort_order for item in rendered.rendered_components] == [10, 20]


def test_render_composition_text_model_is_deterministic_across_reloads() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate", composition_name="Plate")
    flow.add_component_to_composition(composition_id="plate", component_name="A")
    flow.add_component_to_composition(composition_id="plate", component_name="B")
    with_three = flow.add_component_to_composition(composition_id="plate", component_name="C")

    flow.reorder_components_in_composition(
        composition_id="plate",
        ordered_entries=[
            (with_three.components[2].component_id, with_three.components[2].sort_order),
            (with_three.components[0].component_id, with_three.components[0].sort_order),
            (with_three.components[1].component_id, with_three.components[1].sort_order),
        ],
    )

    first = flow.render_composition_text_model(composition_id="plate")
    second = flow.render_composition_text_model(composition_id="plate")

    assert first.text == "Plate: C, A, B"
    assert second.text == first.text
    assert [item.text_token for item in second.rendered_components] == ["C", "A", "B"]


def test_render_composition_text_model_does_not_mix_other_compositions() -> None:
    flow = _build_flow()
    flow.create_composition(composition_id="plate_a", composition_name="Plate A")
    flow.create_composition(composition_id="plate_b", composition_name="Plate B")
    flow.add_component_to_composition(composition_id="plate_a", component_name="Fish")
    flow.add_component_to_composition(composition_id="plate_b", component_name="Soup")

    rendered = flow.render_composition_text_model(composition_id="plate_a")

    assert rendered.text == "Plate A: Fish"
    assert [item.component_name for item in rendered.rendered_components] == ["Fish"]
