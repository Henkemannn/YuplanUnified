from __future__ import annotations

from dataclasses import dataclass, field

_TRAIT_TO_CONFLICT = {
    "milk": "lactose_relevant",
    "lactose": "lactose_relevant",
    "gluten": "gluten_relevant",
    "fish": "fish_relevant",
    "egg": "egg_relevant",
    "nuts": "nut_relevant",
}


@dataclass(frozen=True)
class DietConflictSource:
    conflict_key: str
    triggering_trait_signals: tuple[str, ...] = ()
    source_type: str = ""
    source_id: str = ""
    source_label: str | None = None


@dataclass(frozen=True)
class DietConflictPreview:
    conflicts_present: tuple[str, ...] = ()
    conflict_sources: list[DietConflictSource] = field(default_factory=list)


def build_diet_conflict_preview_from_traits(
    trait_signals: list[str] | tuple[str, ...],
    *,
    source_type: str,
    source_id: str,
    source_label: str | None = None,
) -> DietConflictPreview:
    normalized = [str(signal or "").strip().lower() for signal in trait_signals]
    normalized = [signal for signal in normalized if signal]

    by_conflict: dict[str, set[str]] = {}
    for signal in normalized:
        conflict_key = _TRAIT_TO_CONFLICT.get(signal)
        if not conflict_key:
            continue
        if conflict_key not in by_conflict:
            by_conflict[conflict_key] = set()
        by_conflict[conflict_key].add(signal)

    conflicts_present = tuple(sorted(by_conflict.keys()))
    conflict_sources = [
        DietConflictSource(
            conflict_key=conflict_key,
            triggering_trait_signals=tuple(sorted(by_conflict[conflict_key])),
            source_type=str(source_type or ""),
            source_id=str(source_id or ""),
            source_label=str(source_label or "").strip() or None,
        )
        for conflict_key in conflicts_present
    ]
    return DietConflictPreview(
        conflicts_present=conflicts_present,
        conflict_sources=conflict_sources,
    )


def merge_diet_conflict_previews(previews: list[DietConflictPreview]) -> DietConflictPreview:
    sources: list[DietConflictSource] = []
    for preview in previews:
        sources.extend(list(preview.conflict_sources))

    conflicts_present = tuple(
        sorted({source.conflict_key for source in sources if str(source.conflict_key).strip()})
    )
    ordered_sources = sorted(
        sources,
        key=lambda item: (
            str(item.conflict_key or ""),
            str(item.source_type or ""),
            str(item.source_label or "").lower(),
            str(item.source_id or ""),
        ),
    )
    return DietConflictPreview(
        conflicts_present=conflicts_present,
        conflict_sources=ordered_sources,
    )


__all__ = [
    "DietConflictSource",
    "DietConflictPreview",
    "build_diet_conflict_preview_from_traits",
    "merge_diet_conflict_previews",
]
