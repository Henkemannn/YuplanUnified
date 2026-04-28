from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import re

from .alias_domain import ComponentAlias
from .alias_repository import InMemoryComponentAliasRepository
from .domain import Component

_CONNECTOR_WORDS = {"med", "m", "och", "i", "a"}


@dataclass(frozen=True)
class ComponentPossibleMatch:
    component_id: str
    component_name: str
    matched_on: str
    normalized_text: str
    score: float


@dataclass(frozen=True)
class ComponentMatchResult:
    status: str
    normalized_text: str
    component_id: str | None
    component_name: str | None
    confidence: Decimal | float | None
    possible_matches: list[ComponentPossibleMatch] = field(default_factory=list)


def normalize_component_match_text(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return ""

    tokens = [token for token in normalized.split(" ") if token and token not in _CONNECTOR_WORDS]
    return " ".join(tokens)


def create_component_alias(
    alias_repository: InMemoryComponentAliasRepository,
    *,
    alias_id: str,
    component_id: str,
    alias_text: str,
    source: str = "manual",
    confidence: Decimal | float | None = None,
    components: list[Component] | None = None,
) -> ComponentAlias:
    alias_id_value = str(alias_id or "").strip()
    component_id_value = str(component_id or "").strip()
    alias_text_value = str(alias_text or "").strip()
    source_value = str(source or "").strip()

    if not alias_id_value:
        raise ValueError("alias_id must be non-empty")
    if not component_id_value:
        raise ValueError("component_id must be non-empty")
    if not alias_text_value:
        raise ValueError("alias_text must be non-empty")
    if not source_value:
        raise ValueError("source must be non-empty")

    if components is not None:
        known_ids = {str(item.component_id) for item in components}
        if component_id_value not in known_ids:
            raise ValueError(f"component not found: {component_id_value}")

    alias_norm = normalize_component_match_text(alias_text_value)
    if not alias_norm:
        raise ValueError("alias_text normalization cannot be empty")

    alias = ComponentAlias(
        alias_id=alias_id_value,
        component_id=component_id_value,
        alias_text=alias_text_value,
        alias_norm=alias_norm,
        source=source_value,
        confidence=confidence,
    )
    alias_repository.add(alias)
    return alias


def match_component_reference(
    import_text: str,
    *,
    components: list[Component],
    alias_repository: InMemoryComponentAliasRepository,
) -> ComponentMatchResult:
    normalized_text = normalize_component_match_text(import_text)
    if not normalized_text:
        return ComponentMatchResult(
            status="no_match",
            normalized_text=normalized_text,
            component_id=None,
            component_name=None,
            confidence=None,
            possible_matches=[],
        )

    canonical_matches = [
        component
        for component in components
        if normalize_component_match_text(component.canonical_name) == normalized_text
    ]
    if len(canonical_matches) == 1:
        hit = canonical_matches[0]
        return ComponentMatchResult(
            status="exact_match",
            normalized_text=normalized_text,
            component_id=hit.component_id,
            component_name=hit.canonical_name,
            confidence=Decimal("1.0"),
            possible_matches=[],
        )

    alias_matches = alias_repository.find_by_alias_norm(normalized_text)
    if len(alias_matches) == 1:
        alias = alias_matches[0]
        hit = next((item for item in components if item.component_id == alias.component_id), None)
        if hit is not None:
            return ComponentMatchResult(
                status="alias_match",
                normalized_text=normalized_text,
                component_id=hit.component_id,
                component_name=hit.canonical_name,
                confidence=alias.confidence if alias.confidence is not None else Decimal("0.95"),
                possible_matches=[],
            )

    possible = _find_possible_matches(normalized_text, components, alias_repository)
    if possible:
        best = possible[0]
        return ComponentMatchResult(
            status="possible_match",
            normalized_text=normalized_text,
            component_id=None,
            component_name=None,
            confidence=best.score,
            possible_matches=possible,
        )

    return ComponentMatchResult(
        status="no_match",
        normalized_text=normalized_text,
        component_id=None,
        component_name=None,
        confidence=None,
        possible_matches=[],
    )


def _find_possible_matches(
    normalized_text: str,
    components: list[Component],
    alias_repository: InMemoryComponentAliasRepository,
) -> list[ComponentPossibleMatch]:
    input_tokens = _token_set(normalized_text)
    if not input_tokens:
        return []

    by_component: dict[str, ComponentPossibleMatch] = {}

    for component in components:
        normalized_name = normalize_component_match_text(component.canonical_name)
        score = _token_similarity(input_tokens, _token_set(normalized_name))
        if score >= 0.66:
            by_component[component.component_id] = ComponentPossibleMatch(
                component_id=component.component_id,
                component_name=component.canonical_name,
                matched_on="canonical_name",
                normalized_text=normalized_name,
                score=score,
            )

    for alias in alias_repository.list_all():
        component = next((item for item in components if item.component_id == alias.component_id), None)
        if component is None:
            continue
        score = _token_similarity(input_tokens, _token_set(alias.alias_norm))
        if score < 0.66:
            continue
        existing = by_component.get(component.component_id)
        if existing is None or score > existing.score:
            by_component[component.component_id] = ComponentPossibleMatch(
                component_id=component.component_id,
                component_name=component.canonical_name,
                matched_on="alias",
                normalized_text=alias.alias_norm,
                score=score,
            )

    ordered = sorted(
        by_component.values(),
        key=lambda item: (-item.score, item.component_name.lower(), item.component_id),
    )
    return ordered[:3]


def _token_set(value: str) -> set[str]:
    return {_singularize(token) for token in str(value or "").split(" ") if token}


def _token_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    shared = left.intersection(right)
    if not shared:
        return 0.0
    denominator = float(max(len(left), len(right)))
    return len(shared) / denominator


def _singularize(token: str) -> str:
    value = str(token or "").strip().lower()
    if len(value) <= 4:
        return value
    for suffix in ("arna", "erna", "or", "ar", "er", "na"):
        if value.endswith(suffix) and len(value) - len(suffix) >= 3:
            return value[: -len(suffix)]
    return value
