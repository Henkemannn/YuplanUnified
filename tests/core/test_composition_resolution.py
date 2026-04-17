from __future__ import annotations

from decimal import Decimal

from core.components import Composition, InMemoryCompositionRepository
from core.menu import (
    InMemoryCompositionAliasRepository,
    create_composition_alias,
    normalize_menu_import_text,
    resolve_composition_reference,
)


def test_alias_repository_listing_and_find_behavior() -> None:
    alias_repo = InMemoryCompositionAliasRepository()

    alias_repo.add(
        create_composition_alias(
            alias_repository=InMemoryCompositionAliasRepository(),
            alias_id="tmp",
            composition_id="comp_a",
            alias_text="unused",
        )
    )

    # Use a dedicated repo with explicit rows for assertions.
    alias_repo = InMemoryCompositionAliasRepository()
    alias_repo.add(
        create_composition_alias(
            alias_repository=InMemoryCompositionAliasRepository(),
            alias_id="a1",
            composition_id="comp_a",
            alias_text="Kottbullar med mos",
            source="manual",
            confidence=Decimal("0.9"),
        )
    )
    alias_repo.add(
        create_composition_alias(
            alias_repository=InMemoryCompositionAliasRepository(),
            alias_id="a2",
            composition_id="comp_b",
            alias_text="Fisk m potatis",
            source="import",
        )
    )

    assert len(alias_repo.list_all()) == 2
    assert len(alias_repo.find_by_alias_norm("kottbullar mos")) == 1
    assert len(alias_repo.list_for_composition("comp_b")) == 1


def test_normalization_behavior() -> None:
    assert normalize_menu_import_text("  Kottbullar,  med   mos!  ") == "kottbullar mos"
    assert normalize_menu_import_text("Fisk m potatis och sas") == "fisk potatis sas"
    assert normalize_menu_import_text("Pytt-i-panna") == "pytt i panna"


def test_alias_exact_match_resolves() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(
        Composition(
            composition_id="meatballs_plate",
            composition_name="Kottbullar med mos",
        )
    )
    alias_repo = InMemoryCompositionAliasRepository()
    create_composition_alias(
        alias_repository=alias_repo,
        alias_id="alias_1",
        composition_id="meatballs_plate",
        alias_text="Kottbullar m mos",
        source="manual",
        confidence=Decimal("0.95"),
        composition_repository=composition_repo,
    )

    result = resolve_composition_reference(
        import_text="Kottbullar m mos",
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert result.kind == "composition"
    assert result.composition_id == "meatballs_plate"
    assert result.matched_via == "alias"
    assert result.unresolved_text is None


def test_canonical_name_exact_normalized_match_resolves() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(
        Composition(
            composition_id="fish_plate",
            composition_name="Fisk med potatis",
        )
    )
    alias_repo = InMemoryCompositionAliasRepository()

    result = resolve_composition_reference(
        import_text="  fisk m potatis ",
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert result.kind == "composition"
    assert result.composition_id == "fish_plate"
    assert result.matched_via == "canonical_name"
    assert result.unresolved_text is None


def test_unresolved_fallback_for_non_matching_input() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(Composition(composition_id="a", composition_name="Kottbullar med mos"))
    alias_repo = InMemoryCompositionAliasRepository()

    result = resolve_composition_reference(
        import_text="Totally unknown dish",
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert result.kind == "unresolved"
    assert result.composition_id is None
    assert result.unresolved_text == "Totally unknown dish"


def test_honest_unresolved_for_ambiguous_alias_match() -> None:
    composition_repo = InMemoryCompositionRepository()
    composition_repo.add(Composition(composition_id="a", composition_name="Dish A"))
    composition_repo.add(Composition(composition_id="b", composition_name="Dish B"))

    alias_repo = InMemoryCompositionAliasRepository()
    alias_repo.add(
        create_composition_alias(
            alias_repository=InMemoryCompositionAliasRepository(),
            alias_id="a1",
            composition_id="a",
            alias_text="same alias",
        )
    )
    alias_repo.add(
        create_composition_alias(
            alias_repository=InMemoryCompositionAliasRepository(),
            alias_id="a2",
            composition_id="b",
            alias_text="same alias",
        )
    )

    result = resolve_composition_reference(
        import_text="same alias",
        composition_repository=composition_repo,
        alias_repository=alias_repo,
    )

    assert result.kind == "unresolved"
    assert result.composition_id is None
    assert "ambiguous alias" in " ".join(result.warnings)
