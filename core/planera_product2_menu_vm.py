from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .commun_builder_projection import CommunMenuProjectionRow


_SUPPORTED_OPTION_VARIANTS = {"main", "alt1", "alt2", "alt3", "alt4", "alt5"}
_DISPLAY_LABELS = {
    "main": "Main",
    "alt1": "Alt 1",
    "alt2": "Alt 2",
    "alt3": "Alt 3",
    "alt4": "Alt 4",
    "alt5": "Alt 5",
}


class Product2MealOptionsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Product2MealOptionVM:
    option_id: str
    variant_type: str
    display_label: str
    sort_order: int
    display_title: str
    composition_id: str | None
    resolved: bool
    source_error: str | None = None


@dataclass(frozen=True, slots=True)
class Product2MealOptionsVM:
    day: str
    meal: str
    options: tuple[Product2MealOptionVM, ...]


def _display_label_for_variant(variant_type: str) -> str:
    return _DISPLAY_LABELS.get(variant_type, variant_type)


def _coerce_text(value: object) -> str:
    return value if isinstance(value, str) else str(value or "")


def _build_option(row: CommunMenuProjectionRow) -> Product2MealOptionVM:
    variant_type = str(row.variant_type or "").strip().lower()
    if variant_type not in _SUPPORTED_OPTION_VARIANTS:
        raise Product2MealOptionsError(f"unsupported option variant: {variant_type or '<empty>'}")

    display_title = _coerce_text(row.text)
    if not display_title.strip():
        raise Product2MealOptionsError(f"empty display title for option {row.builder_menu_row_id}")

    return Product2MealOptionVM(
        option_id=str(row.builder_menu_row_id),
        variant_type=variant_type,
        display_label=_display_label_for_variant(variant_type),
        sort_order=int(row.sort_order),
        display_title=display_title,
        composition_id=str(row.composition_id) if row.composition_id is not None else None,
        resolved=bool(row.resolved),
        source_error=str(row.error) if row.error else None,
    )


def build_product2_meal_options_vm(
    rows: Iterable[CommunMenuProjectionRow],
    *,
    day: str,
    meal: str,
) -> Product2MealOptionsVM:
    matching_rows: list[CommunMenuProjectionRow] = []
    for row in rows:
        if str(row.day) != day or str(row.meal) != meal:
            continue
        variant_type = str(row.variant_type or "").strip().lower()
        if variant_type == "dessert":
            continue
        if variant_type == "unresolved_variant":
            raise Product2MealOptionsError(f"unresolved option slot for {day}/{meal}")
        if variant_type not in _SUPPORTED_OPTION_VARIANTS:
            raise Product2MealOptionsError(f"unsupported option variant: {variant_type or '<empty>'}")
        matching_rows.append(row)

    sorted_rows = sorted(matching_rows, key=lambda row: (int(row.sort_order), str(row.builder_menu_row_id)))
    options = tuple(_build_option(row) for row in sorted_rows)
    return Product2MealOptionsVM(day=day, meal=meal, options=options)