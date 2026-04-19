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
