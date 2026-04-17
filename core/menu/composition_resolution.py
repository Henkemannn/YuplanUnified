from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import re

from ..components.composition_repository import InMemoryCompositionRepository
from .alias_domain import CompositionAlias
from .alias_repository import InMemoryCompositionAliasRepository

_CONNECTOR_WORDS = {"med", "m", "och"}


@dataclass(frozen=True)
class CompositionResolutionResult:
    kind: str
    composition_id: str | None
    unresolved_text: str | None
    normalized_text: str
    matched_via: str | None
    confidence: Decimal | float | None
    warnings: list[str] = field(default_factory=list)


def normalize_menu_import_text(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return ""

    tokens = [token for token in normalized.split(" ") if token and token not in _CONNECTOR_WORDS]
    return " ".join(tokens)


def resolve_composition_reference(
    import_text: str,
    composition_repository: InMemoryCompositionRepository,
    alias_repository: InMemoryCompositionAliasRepository,
) -> CompositionResolutionResult:
    normalized_text = normalize_menu_import_text(import_text)
    raw_text = str(import_text or "").strip()

    if not normalized_text:
        return CompositionResolutionResult(
            kind="unresolved",
            composition_id=None,
            unresolved_text=raw_text,
            normalized_text=normalized_text,
            matched_via=None,
            confidence=None,
            warnings=["empty or non-meaningful menu text; unresolved"],
        )

    alias_matches = alias_repository.find_by_alias_norm(normalized_text)
    if len(alias_matches) == 1:
        match = alias_matches[0]
        return CompositionResolutionResult(
            kind="composition",
            composition_id=match.composition_id,
            unresolved_text=None,
            normalized_text=normalized_text,
            matched_via="alias",
            confidence=match.confidence if match.confidence is not None else Decimal("1.0"),
            warnings=[],
        )
    if len(alias_matches) > 1:
        return CompositionResolutionResult(
            kind="unresolved",
            composition_id=None,
            unresolved_text=raw_text,
            normalized_text=normalized_text,
            matched_via=None,
            confidence=None,
            warnings=["ambiguous alias match; unresolved"],
        )

    canonical_matches = [
        composition
        for composition in composition_repository.list_all()
        if normalize_menu_import_text(composition.composition_name) == normalized_text
    ]

    if len(canonical_matches) == 1:
        match = canonical_matches[0]
        return CompositionResolutionResult(
            kind="composition",
            composition_id=match.composition_id,
            unresolved_text=None,
            normalized_text=normalized_text,
            matched_via="canonical_name",
            confidence=Decimal("1.0"),
            warnings=[],
        )

    if len(canonical_matches) > 1:
        return CompositionResolutionResult(
            kind="unresolved",
            composition_id=None,
            unresolved_text=raw_text,
            normalized_text=normalized_text,
            matched_via=None,
            confidence=None,
            warnings=["ambiguous canonical composition name match; unresolved"],
        )

    return CompositionResolutionResult(
        kind="unresolved",
        composition_id=None,
        unresolved_text=raw_text,
        normalized_text=normalized_text,
        matched_via=None,
        confidence=None,
        warnings=["no composition match found; unresolved"],
    )


def create_composition_alias(
    alias_repository: InMemoryCompositionAliasRepository,
    *,
    alias_id: str,
    composition_id: str,
    alias_text: str,
    source: str = "manual",
    confidence: Decimal | float | None = None,
    composition_repository: InMemoryCompositionRepository | None = None,
) -> CompositionAlias:
    alias_id_value = str(alias_id or "").strip()
    composition_id_value = str(composition_id or "").strip()
    alias_text_value = str(alias_text or "").strip()
    source_value = str(source or "").strip()
    if not alias_id_value:
        raise ValueError("alias_id must be non-empty")
    if not composition_id_value:
        raise ValueError("composition_id must be non-empty")
    if not alias_text_value:
        raise ValueError("alias_text must be non-empty")
    if not source_value:
        raise ValueError("source must be non-empty")

    if composition_repository is not None and composition_repository.get(composition_id_value) is None:
        raise ValueError(f"composition not found: {composition_id_value}")

    alias_norm = normalize_menu_import_text(alias_text_value)
    if not alias_norm:
        raise ValueError("alias_text normalization cannot be empty")

    alias = CompositionAlias(
        alias_id=alias_id_value,
        composition_id=composition_id_value,
        alias_text=alias_text_value,
        alias_norm=alias_norm,
        source=source_value,
        confidence=confidence,
    )
    alias_repository.add(alias)
    return alias
