from __future__ import annotations

from core.builder.diet_conflict_preview import (
    build_diet_conflict_preview_from_traits,
    merge_diet_conflict_previews,
)


def test_diet_conflict_preview_maps_trait_signals_deterministically() -> None:
    preview = build_diet_conflict_preview_from_traits(
        ["fish", "milk", "egg", "gluten", "nuts", "fish", "unknown"],
        source_type="ingredient_line",
        source_id="line_1",
        source_label="Cod",
    )

    assert preview.conflicts_present == (
        "egg_relevant",
        "fish_relevant",
        "gluten_relevant",
        "lactose_relevant",
        "nut_relevant",
    )
    assert [source.conflict_key for source in preview.conflict_sources] == list(preview.conflicts_present)
    assert preview.conflict_sources[0].source_type == "ingredient_line"
    assert preview.conflict_sources[0].source_id == "line_1"


def test_diet_conflict_preview_merge_is_deterministic() -> None:
    a = build_diet_conflict_preview_from_traits(
        ["fish"],
        source_type="ingredient_line",
        source_id="line_a",
        source_label="Cod",
    )
    b = build_diet_conflict_preview_from_traits(
        ["milk", "gluten"],
        source_type="ingredient_line",
        source_id="line_b",
        source_label="Flour milk",
    )

    merged = merge_diet_conflict_previews([b, a])

    assert merged.conflicts_present == (
        "fish_relevant",
        "gluten_relevant",
        "lactose_relevant",
    )
    assert [source.conflict_key for source in merged.conflict_sources] == [
        "fish_relevant",
        "gluten_relevant",
        "lactose_relevant",
    ]
