from __future__ import annotations

from dataclasses import dataclass, field

from .diet_conflict_preview import DietConflictPreview


@dataclass(frozen=True)
class IngredientTraitSource:
    recipe_id: str
    recipe_ingredient_line_id: str
    ingredient_name: str
    trait_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentDeclarationReadiness:
    component_id: str
    component_name: str
    primary_recipe_id: str | None
    trait_signals_present: tuple[str, ...] = ()
    conflict_preview: DietConflictPreview = field(default_factory=DietConflictPreview)
    ingredient_sources: list[IngredientTraitSource] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompositionDeclarationReadiness:
    composition_id: str
    composition_name: str
    trait_signals_present: tuple[str, ...] = ()
    conflict_preview: DietConflictPreview = field(default_factory=DietConflictPreview)
    components: list[ComponentDeclarationReadiness] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MenuRowDeclarationReadiness:
    menu_detail_id: str
    composition_ref_type: str
    composition_id: str | None
    composition_name: str | None
    trait_signals_present: tuple[str, ...] = ()
    conflict_preview: DietConflictPreview = field(default_factory=DietConflictPreview)
    components: list[ComponentDeclarationReadiness] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MenuDeclarationReadiness:
    menu_id: str
    trait_signals_present: tuple[str, ...] = ()
    conflict_preview: DietConflictPreview = field(default_factory=DietConflictPreview)
    rows: list[MenuRowDeclarationReadiness] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
