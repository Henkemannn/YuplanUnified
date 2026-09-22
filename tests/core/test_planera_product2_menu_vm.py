from __future__ import annotations

import pytest

from core.commun_builder_projection import CommunMenuProjectionRow
from core.planera_product2_menu_vm import (
    Product2MealOptionsError,
    build_product2_meal_options_vm,
)


def _row(
    *,
    day: str = "mon",
    meal: str = "lunch",
    variant_type: str,
    sort_order: int,
    builder_menu_row_id: str,
    composition_id: str | None = None,
    resolved: bool = True,
    text: str = "Dish",
    unresolved_text: str | None = None,
    error: str | None = None,
) -> CommunMenuProjectionRow:
    return CommunMenuProjectionRow(
        day=day,
        meal=meal,
        variant_type=variant_type,
        sort_order=sort_order,
        builder_menu_id="menu-1",
        builder_menu_version=1,
        builder_menu_row_id=builder_menu_row_id,
        composition_id=composition_id,
        resolved=resolved,
        text=text,
        unresolved_text=unresolved_text,
        error=error,
    )


def test_two_resolved_options_alt1_alt2():
    vm = build_product2_meal_options_vm(
        [
            _row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", composition_id="comp-a", text="Fläskkarré"),
            _row(variant_type="alt2", sort_order=20, builder_menu_row_id="row-b", composition_id="comp-b", text="Kokt torsk"),
        ],
        day="mon",
        meal="lunch",
    )

    assert vm.day == "mon"
    assert vm.meal == "lunch"
    assert [option.display_title for option in vm.options] == ["Fläskkarré", "Kokt torsk"]


def test_ordering_by_sort_order():
    vm = build_product2_meal_options_vm(
        [
            _row(variant_type="alt2", sort_order=20, builder_menu_row_id="row-b", text="Second"),
            _row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="First"),
        ],
        day="mon",
        meal="lunch",
    )

    assert [option.option_id for option in vm.options] == ["row-a", "row-b"]


def test_tie_ordering_by_builder_menu_row_id():
    vm = build_product2_meal_options_vm(
        [
            _row(variant_type="alt2", sort_order=10, builder_menu_row_id="row-b", text="Second"),
            _row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="First"),
        ],
        day="mon",
        meal="lunch",
    )

    assert [option.option_id for option in vm.options] == ["row-a", "row-b"]


@pytest.mark.parametrize("variant_type", ["main", "alt3", "alt4", "alt5"])
def test_additional_supported_variants_are_accepted(variant_type: str):
    vm = build_product2_meal_options_vm(
        [_row(variant_type=variant_type, sort_order=10, builder_menu_row_id=f"row-{variant_type}", text="Dish")],
        day="mon",
        meal="lunch",
    )

    assert vm.options[0].variant_type == variant_type


def test_dessert_is_excluded_from_options():
    vm = build_product2_meal_options_vm(
        [
            _row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="Main dish"),
            _row(variant_type="dessert", sort_order=20, builder_menu_row_id="row-dessert", text="Cake"),
        ],
        day="mon",
        meal="lunch",
    )

    assert [option.option_id for option in vm.options] == ["row-a"]


def test_other_day_is_excluded():
    vm = build_product2_meal_options_vm(
        [
            _row(day="tue", variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="Tuesday dish"),
        ],
        day="mon",
        meal="lunch",
    )

    assert vm.options == ()


def test_other_meal_is_excluded():
    vm = build_product2_meal_options_vm(
        [
            _row(meal="dinner", variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="Dinner dish"),
        ],
        day="mon",
        meal="lunch",
    )

    assert vm.options == ()


def test_unresolved_free_text_alt2_remains_an_option():
    vm = build_product2_meal_options_vm(
        [
            _row(
                variant_type="alt2",
                sort_order=10,
                builder_menu_row_id="row-a",
                composition_id=None,
                resolved=False,
                text="Vegetarisk lasagne",
                unresolved_text="Vegetarisk lasagne",
            ),
        ],
        day="mon",
        meal="lunch",
    )

    assert vm.options[0].display_title == "Vegetarisk lasagne"
    assert vm.options[0].resolved is False


def test_display_title_uses_canonical_row_text_unchanged():
    vm = build_product2_meal_options_vm(
        [_row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="  Canonical title  ")],
        day="mon",
        meal="lunch",
    )

    assert vm.options[0].display_title == "  Canonical title  "


def test_duplicate_composition_id_produces_distinct_options():
    vm = build_product2_meal_options_vm(
        [
            _row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", composition_id="comp-x", text="First"),
            _row(variant_type="alt2", sort_order=20, builder_menu_row_id="row-b", composition_id="comp-x", text="Second"),
        ],
        day="mon",
        meal="lunch",
    )

    assert [option.option_id for option in vm.options] == ["row-a", "row-b"]
    assert [option.composition_id for option in vm.options] == ["comp-x", "comp-x"]


def test_option_id_equals_builder_menu_row_id():
    vm = build_product2_meal_options_vm(
        [_row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="Dish")],
        day="mon",
        meal="lunch",
    )

    assert vm.options[0].option_id == "row-a"


def test_unresolved_variant_fails_closed():
    with pytest.raises(Product2MealOptionsError, match="unresolved option slot"):
        build_product2_meal_options_vm(
            [_row(variant_type="unresolved_variant", sort_order=10, builder_menu_row_id="row-a", text="Dish")],
            day="mon",
            meal="lunch",
        )


def test_unknown_variant_fails_closed():
    with pytest.raises(Product2MealOptionsError, match="unsupported option variant"):
        build_product2_meal_options_vm(
            [_row(variant_type="side", sort_order=10, builder_menu_row_id="row-a", text="Dish")],
            day="mon",
            meal="lunch",
        )


def test_empty_title_for_selectable_option_fails_closed():
    with pytest.raises(Product2MealOptionsError, match="empty display title"):
        build_product2_meal_options_vm(
            [_row(variant_type="alt1", sort_order=10, builder_menu_row_id="row-a", text="   ")],
            day="mon",
            meal="lunch",
        )


def test_no_matching_options_returns_empty_collection():
    vm = build_product2_meal_options_vm([], day="mon", meal="lunch")

    assert vm.options == ()