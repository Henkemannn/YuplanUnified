from __future__ import annotations

import pytest

from core.components import CompositionService


def test_create_composition() -> None:
    service = CompositionService()

    composition = service.create_composition(
        composition_id="meatballs_plate",
        composition_name="Meatballs Plate",
        library_group="lunch",
    )

    assert composition.composition_id == "meatballs_plate"
    assert composition.composition_name == "Meatballs Plate"
    assert composition.library_group == "lunch"
    assert composition.components == []
    assert composition.use_custom_menu_name is False
    assert composition.menu_name is None
    assert composition.effective_menu_name == "Meatballs Plate"


def test_custom_menu_name_toggles_without_losing_stored_value() -> None:
    service = CompositionService()
    service.create_composition(
        composition_id="plate",
        composition_name="Lasagne",
    )

    updated = service.update_composition_metadata(
        composition_id="plate",
        use_custom_menu_name=True,
        menu_name="  Hemlagad lasagne med tomat, béchamel och parmesan  ",
    )

    assert updated.use_custom_menu_name is True
    assert updated.menu_name == "Hemlagad lasagne med tomat, béchamel och parmesan"
    assert updated.effective_menu_name == "Hemlagad lasagne med tomat, béchamel och parmesan"

    disabled = service.update_composition_metadata(
        composition_id="plate",
        use_custom_menu_name=False,
    )

    assert disabled.use_custom_menu_name is False
    assert disabled.menu_name == "Hemlagad lasagne med tomat, béchamel och parmesan"
    assert disabled.effective_menu_name == "Lasagne"


def test_custom_menu_name_requires_effective_value_when_enabled() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Lasagne")

    with pytest.raises(ValueError, match="menu_name must be non-empty when use_custom_menu_name is true"):
        service.update_composition_metadata(
            composition_id="plate",
            use_custom_menu_name=True,
            menu_name="   ",
        )


def test_add_components_to_composition_and_preserve_order() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Plate")

    service.add_component_to_composition(
        composition_id="plate",
        component_id="sauce",
        role="sauce",
        sort_order=30,
    )
    service.add_component_to_composition(
        composition_id="plate",
        component_id="main",
        role="main",
        sort_order=10,
    )
    updated = service.add_component_to_composition(
        composition_id="plate",
        component_id="side",
        role="side",
        sort_order=20,
    )

    assert [item.component_id for item in updated.components] == ["main", "side", "sauce"]
    assert [item.sort_order for item in updated.components] == [10, 20, 30]


def test_list_compositions() -> None:
    service = CompositionService()
    service.create_composition(composition_id="a", composition_name="A")
    service.create_composition(composition_id="b", composition_name="B")

    compositions = service.list_compositions()

    assert {composition.composition_id for composition in compositions} == {"a", "b"}


def test_list_compositions_by_group() -> None:
    service = CompositionService()
    service.create_composition(composition_id="a", composition_name="A", library_group="lunch")
    service.create_composition(composition_id="b", composition_name="B", library_group="dinner")
    service.create_composition(composition_id="c", composition_name="C", library_group="lunch")

    lunch = service.list_compositions(group_name="lunch")

    assert {composition.composition_id for composition in lunch} == {"a", "c"}


def test_update_composition_metadata_updates_name_and_group_without_touching_components() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Plate", library_group="ovrigt")
    service.add_component_to_composition(
        composition_id="plate",
        component_id="fish",
        component_name="Fish",
        role="main",
        sort_order=10,
    )

    updated = service.update_composition_metadata(
        composition_id="plate",
        composition_name="Updated Plate",
        library_group="fisk",
    )

    assert updated.composition_name == "Updated Plate"
    assert updated.library_group == "fisk"
    assert [item.component_id for item in updated.components] == ["fish"]


def test_component_mutations_preserve_custom_menu_name_fields() -> None:
    service = CompositionService()
    service.create_composition(
        composition_id="plate",
        composition_name="Plate",
        use_custom_menu_name=True,
        menu_name="Custom plate",
    )

    added = service.add_component_to_composition(
        composition_id="plate",
        component_id="fish",
        role="main",
        sort_order=10,
    )
    rerolled = service.update_component_role_in_composition(
        composition_id="plate",
        component_id="fish",
        role="side",
    )
    reordered = service.reorder_components_in_composition(
        composition_id="plate",
        ordered_entries=[("fish", 10)],
    )
    removed = service.remove_component_from_composition(
        composition_id="plate",
        component_id="fish",
        sort_order=10,
    )

    for item in (added, rerolled, reordered, removed):
        assert item.use_custom_menu_name is True
        assert item.menu_name == "Custom plate"
        assert item.effective_menu_name == "Custom plate"


def test_duplicate_component_allowed_when_sort_order_differs() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Plate")

    service.add_component_to_composition(
        composition_id="plate",
        component_id="potatoes",
        role="side",
        sort_order=10,
    )
    updated = service.add_component_to_composition(
        composition_id="plate",
        component_id="potatoes",
        role="side_extra",
        sort_order=20,
    )

    assert [item.component_id for item in updated.components] == ["potatoes", "potatoes"]
    assert [item.sort_order for item in updated.components] == [10, 20]


def test_duplicate_component_same_sort_order_rejected() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Plate")
    service.add_component_to_composition(
        composition_id="plate",
        component_id="potatoes",
        sort_order=10,
    )

    with pytest.raises(ValueError, match="duplicate component entry"):
        service.add_component_to_composition(
            composition_id="plate",
            component_id="potatoes",
            sort_order=10,
        )


def test_remove_component_from_composition_by_sort_order() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Plate")
    service.add_component_to_composition(
        composition_id="plate",
        component_id="potatoes",
        sort_order=10,
    )
    service.add_component_to_composition(
        composition_id="plate",
        component_id="potatoes",
        sort_order=20,
    )

    updated = service.remove_component_from_composition(
        composition_id="plate",
        component_id="potatoes",
        sort_order=10,
    )

    assert len(updated.components) == 1
    assert updated.components[0].sort_order == 20


def test_update_component_role_in_composition() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Plate")
    service.add_component_to_composition(
        composition_id="plate",
        component_id="potatoes",
        role="side",
        sort_order=10,
    )

    updated = service.update_component_role_in_composition(
        composition_id="plate",
        component_id="potatoes",
        role="carb",
    )

    assert len(updated.components) == 1
    assert updated.components[0].component_id == "potatoes"
    assert updated.components[0].role == "carb"


def test_update_component_role_in_composition_allows_clearing_role() -> None:
    service = CompositionService()
    service.create_composition(composition_id="plate", composition_name="Plate")
    service.add_component_to_composition(
        composition_id="plate",
        component_id="potatoes",
        role="side",
        sort_order=10,
    )

    updated = service.update_component_role_in_composition(
        composition_id="plate",
        component_id="potatoes",
        role="   ",
    )

    assert len(updated.components) == 1
    assert updated.components[0].role is None


def test_invalid_ids_and_names_rejected() -> None:
    service = CompositionService()

    with pytest.raises(ValueError, match="composition_id must be non-empty"):
        service.create_composition(composition_id="", composition_name="Valid")

    with pytest.raises(ValueError, match="composition_name must be non-empty"):
        service.create_composition(composition_id="valid", composition_name="")

    service.create_composition(composition_id="plate", composition_name="Plate")
    with pytest.raises(ValueError, match="component_id must be non-empty"):
        service.add_component_to_composition(composition_id="plate", component_id="")
