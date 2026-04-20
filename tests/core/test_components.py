from __future__ import annotations

import pytest

from core.components import ComponentService


def test_create_component() -> None:
    service = ComponentService()

    component = service.create_component(
        component_id="meatballs",
        canonical_name="Meatballs",
        default_uom="kg",
        tags=["protein"],
        categories=["main"],
    )

    assert component.component_id == "meatballs"
    assert component.canonical_name == "Meatballs"
    assert component.is_active is True
    assert component.default_uom == "kg"
    assert component.tags == ["protein"]
    assert component.categories == ["main"]


def test_fetch_component_by_id() -> None:
    service = ComponentService()
    service.create_component(component_id="tomato_sauce", canonical_name="Tomato Sauce")

    fetched = service.get_component("tomato_sauce")

    assert fetched is not None
    assert fetched.component_id == "tomato_sauce"


def test_list_components() -> None:
    service = ComponentService()
    service.create_component(component_id="potatoes", canonical_name="Potatoes")
    service.create_component(component_id="fish_timbal", canonical_name="Fish Timbal")

    components = service.list_components()

    assert len(components) == 2
    assert {c.component_id for c in components} == {"potatoes", "fish_timbal"}


def test_active_filter() -> None:
    service = ComponentService()
    service.create_component(component_id="mayonnaise_sauce", canonical_name="Mayonnaise Sauce", is_active=True)
    service.create_component(component_id="legacy_sauce", canonical_name="Legacy Sauce", is_active=False)

    active_components = service.list_components(active_only=True)

    assert len(active_components) == 1
    assert active_components[0].component_id == "mayonnaise_sauce"


def test_duplicate_component_id_raises() -> None:
    service = ComponentService()
    service.create_component(component_id="meatballs", canonical_name="Meatballs")

    with pytest.raises(ValueError, match="component already exists"):
        service.create_component(component_id="meatballs", canonical_name="Meatballs V2")


def test_set_primary_recipe_id_for_component() -> None:
    service = ComponentService()
    service.create_component(component_id="meatballs", canonical_name="Meatballs")

    updated = service.set_primary_recipe_id(component_id="meatballs", recipe_id="r1")

    assert updated.primary_recipe_id == "r1"
    fetched = service.get_component("meatballs")
    assert fetched is not None
    assert fetched.primary_recipe_id == "r1"


def test_set_primary_recipe_id_can_clear_value() -> None:
    service = ComponentService()
    service.create_component(component_id="fish", canonical_name="Fish")
    service.set_primary_recipe_id(component_id="fish", recipe_id="r1")

    updated = service.set_primary_recipe_id(component_id="fish", recipe_id="   ")

    assert updated.primary_recipe_id is None
