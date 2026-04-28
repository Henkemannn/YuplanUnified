from __future__ import annotations

from core.components import (
    Component,
    InMemoryComponentAliasRepository,
    create_component_alias,
    match_component_reference,
    normalize_component_match_text,
)


def test_component_match_exact_canonical() -> None:
    alias_repo = InMemoryComponentAliasRepository()
    components = [
        Component(component_id="kokt_potatis", canonical_name="Kokt potatis"),
    ]

    result = match_component_reference(
        "Kokt potatis",
        components=components,
        alias_repository=alias_repo,
    )

    assert result.status == "exact_match"
    assert result.component_id == "kokt_potatis"


def test_component_match_alias() -> None:
    alias_repo = InMemoryComponentAliasRepository()
    components = [
        Component(component_id="kokt_potatis", canonical_name="Kokt potatis"),
    ]
    create_component_alias(
        alias_repository=alias_repo,
        alias_id="cmp_alias_1",
        component_id="kokt_potatis",
        alias_text="potatis kokt",
        components=components,
    )

    result = match_component_reference(
        "Potatis kokt",
        components=components,
        alias_repository=alias_repo,
    )

    assert result.status == "alias_match"
    assert result.component_id == "kokt_potatis"


def test_component_match_no_match() -> None:
    alias_repo = InMemoryComponentAliasRepository()
    components = [
        Component(component_id="kokt_potatis", canonical_name="Kokt potatis"),
    ]

    result = match_component_reference(
        "Stekt fisk",
        components=components,
        alias_repository=alias_repo,
    )

    assert result.status == "no_match"
    assert result.component_id is None


def test_component_match_possible_match_is_reported() -> None:
    alias_repo = InMemoryComponentAliasRepository()
    components = [
        Component(component_id="kokt_potatis", canonical_name="Kokt potatis"),
    ]

    result = match_component_reference(
        "Kokt potatisar",
        components=components,
        alias_repository=alias_repo,
    )

    assert result.status == "possible_match"
    assert result.component_id is None
    assert len(result.possible_matches) == 1
    assert result.possible_matches[0].component_id == "kokt_potatis"


def test_component_match_normalization() -> None:
    assert normalize_component_match_text("  Stekt lök, potatis!  ") == "stekt lök potatis"
