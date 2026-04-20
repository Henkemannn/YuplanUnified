from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
import secrets

from ..components import (
    Component,
    ComponentService,
    Composition,
    CompositionService,
    InMemoryCompositionRepository,
)
from ..menu import (
    InMemoryCompositionAliasRepository,
    create_composition_alias,
    normalize_menu_import_text,
    resolve_composition_reference,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LibraryImportRowResult:
    raw_text: str
    kind: str
    composition_id: str
    composition_name: str
    matched_via: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LibraryImportSummary:
    imported_count: int
    created_count: int
    reused_count: int
    row_results: list[LibraryImportRowResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BuilderFlow:
    def __init__(
        self,
        *,
        component_service: ComponentService,
        composition_service: CompositionService,
        composition_repository: InMemoryCompositionRepository,
        alias_repository: InMemoryCompositionAliasRepository,
    ) -> None:
        self._component_service = component_service
        self._composition_service = composition_service
        self._composition_repository = composition_repository
        self._alias_repository = alias_repository

    def create_standalone_component(self, component_name: str) -> Component:
        name_value = self._normalize_component_name(component_name)
        if not name_value:
            raise ValueError("component_name must be non-empty")

        normalized_key = self._normalize_component_key(name_value)
        for existing_item in self._component_service.list_components(active_only=False):
            if self._normalize_component_key(existing_item.canonical_name) == normalized_key:
                return existing_item

        base = self._slugify_component_name(name_value)
        if not base:
            base = self._generate_component_seed()

        component_id = base
        suffix = 2
        while True:
            existing = self._component_service.get_component(component_id)
            if existing is None:
                break
            if existing.canonical_name == name_value:
                return existing
            component_id = f"{base}_{suffix}"
            suffix += 1

        return self._component_service.create_component(
            component_id=component_id,
            canonical_name=name_value,
        )

    def create_composition(
        self,
        composition_id: str,
        composition_name: str,
        *,
        library_group: str | None = None,
    ) -> Composition:
        return self._composition_service.create_composition(
            composition_id=composition_id,
            composition_name=composition_name,
            library_group=library_group,
        )

    def create_composition_with_generated_id(
        self,
        composition_name: str,
        *,
        library_group: str | None = None,
        seed_components: bool = False,
    ) -> Composition:
        composition, _ = self.create_library_composition_from_text(
            raw_text=composition_name,
            library_group=library_group,
            seed_components=seed_components,
            learn_alias=False,
        )
        return composition

    def add_component_to_composition(
        self,
        composition_id: str,
        component_name: str,
        *,
        role: str | None = None,
    ) -> Composition:
        composition = self._composition_service.get_composition(composition_id)
        if composition is None:
            raise ValueError(f"composition not found: {composition_id}")

        component_name_value = str(component_name or "").strip()
        if not component_name_value:
            raise ValueError("component_name must be non-empty")

        component = self.create_standalone_component(component_name_value)
        return self._composition_service.add_component_to_composition(
            composition_id=composition_id,
            component_id=component.component_id,
            component_name=component.canonical_name,
            role=role,
        )

    def remove_component_from_composition(
        self,
        composition_id: str,
        component_id: str,
    ) -> Composition:
        return self._composition_service.remove_component_from_composition(
            composition_id=composition_id,
            component_id=component_id,
        )

    def rename_component_in_composition(
        self,
        composition_id: str,
        component_id: str,
        new_component_name: str,
        *,
        role: str | None = None,
        role_provided: bool = False,
    ) -> Composition:
        composition = self._composition_service.get_composition(composition_id)
        if composition is None:
            raise ValueError(f"composition not found: {composition_id}")

        new_name_value = str(new_component_name or "").strip()
        if not new_name_value:
            raise ValueError("component_name must be non-empty")

        existing = next(
            (item for item in composition.components if item.component_id == str(component_id)),
            None,
        )
        if existing is None:
            raise ValueError("component entry not found in composition")

        self._composition_service.remove_component_from_composition(
            composition_id=composition_id,
            component_id=str(component_id),
            sort_order=existing.sort_order,
        )
        updated_composition = self._composition_service.get_composition(composition_id)
        if updated_composition is None:
            raise ValueError(f"composition not found: {composition_id}")

        resolved_component = self.create_standalone_component(new_name_value)
        resolved_role = role if role_provided else existing.role
        return self._composition_service.add_component_to_composition(
            composition_id=composition_id,
            component_id=resolved_component.component_id,
            component_name=resolved_component.canonical_name,
            role=resolved_role,
            sort_order=existing.sort_order,
        )

    def update_component_role_in_composition(
        self,
        composition_id: str,
        component_id: str,
        *,
        role: str | None,
    ) -> Composition:
        composition = self._composition_service.get_composition(composition_id)
        if composition is None:
            raise ValueError(f"composition not found: {composition_id}")

        return self._composition_service.update_component_role_in_composition(
            composition_id=composition_id,
            component_id=component_id,
            role=role,
        )

    def list_compositions(self, *, group_name: str | None = None) -> list[Composition]:
        return self._composition_service.list_compositions(group_name=group_name)

    def list_library_components(self) -> list[Component]:
        items = self._component_service.list_components(active_only=False)
        return sorted(items, key=lambda item: (item.canonical_name.lower(), item.component_id))

    def list_reusable_components_for_builder(self, *, query: str | None = None) -> list[Component]:
        items = self.list_library_components()
        query_value = str(query or "").strip().lower()
        if not query_value:
            return items

        return [
            item
            for item in items
            if query_value in item.canonical_name.lower() or query_value in item.component_id.lower()
        ]

    def attach_existing_component_to_composition(
        self,
        *,
        composition_id: str,
        component_id: str,
        role: str | None = None,
    ) -> Composition:
        composition_id_value = str(composition_id or "").strip()
        if not composition_id_value:
            raise ValueError("composition_id must be non-empty")

        component_id_value = str(component_id or "").strip()
        if not component_id_value:
            raise ValueError("component_id must be non-empty")

        composition = self._composition_service.get_composition(composition_id_value)
        if composition is None:
            raise ValueError(f"composition not found: {composition_id_value}")

        component = self._component_service.get_component(component_id_value)
        if component is None:
            raise ValueError(f"component not found: {component_id_value}")

        if any(item.component_id == component_id_value for item in composition.components):
            raise ValueError("component already exists in composition")

        return self._composition_service.add_component_to_composition(
            composition_id=composition_id_value,
            component_id=component.component_id,
            component_name=component.canonical_name,
            role=role,
        )

    def list_library_compositions(self) -> list[Composition]:
        items = self._composition_service.list_compositions()
        return sorted(items, key=lambda item: (item.composition_name.lower(), item.composition_id))

    def import_library_text_lines(self, lines: list[str]) -> LibraryImportSummary:
        normalized_lines = [str(line or "").strip() for line in lines]
        normalized_lines = [line for line in normalized_lines if line]
        if not normalized_lines:
            raise ValueError("lines must contain at least one non-empty text")

        row_results: list[LibraryImportRowResult] = []
        summary_warnings: list[str] = []
        created_count = 0
        reused_count = 0

        for line in normalized_lines:
            resolution = resolve_composition_reference(
                import_text=line,
                composition_repository=self._composition_repository,
                alias_repository=self._alias_repository,
            )

            warnings = list(resolution.warnings)
            matched_via = str(resolution.matched_via or "")
            composition = None

            if resolution.kind == "composition" and resolution.composition_id:
                composition = self._composition_repository.get(resolution.composition_id)
                if composition is not None:
                    reused_count += 1
                    matched_via = matched_via or "existing"

            if composition is None:
                composition, create_warnings = self.create_library_composition_from_text(
                    raw_text=line,
                    library_group=None,
                    seed_components=True,
                    learn_alias=True,
                )
                created_count += 1
                matched_via = "created"
                warnings.extend(create_warnings)

            row_results.append(
                LibraryImportRowResult(
                    raw_text=line,
                    kind="composition",
                    composition_id=composition.composition_id,
                    composition_name=composition.composition_name,
                    matched_via=matched_via,
                    warnings=warnings,
                )
            )
            summary_warnings.extend(warnings)

        return LibraryImportSummary(
            imported_count=len(normalized_lines),
            created_count=created_count,
            reused_count=reused_count,
            row_results=row_results,
            warnings=summary_warnings,
        )

    def create_library_composition_from_text(
        self,
        *,
        raw_text: str,
        library_group: str | None,
        seed_components: bool,
        learn_alias: bool,
        alias_text: str | None = None,
        composition_name_override: str | None = None,
    ) -> tuple[Composition, list[str]]:
        chosen_name = composition_name_override if composition_name_override is not None else raw_text
        composition_name = self._normalize_component_name(chosen_name)
        if not composition_name:
            raise ValueError("composition_name must be non-empty")

        composition = self.create_composition(
            composition_id=self._generate_composition_id(),
            composition_name=composition_name,
            library_group=library_group,
        )
        warnings: list[str] = []

        if seed_components:
            for suggestion in self._suggest_components_from_unresolved_text(raw_text):
                composition = self.add_component_to_composition(
                    composition_id=composition.composition_id,
                    component_name=suggestion,
                    role="component",
                )

        if learn_alias:
            alias_warning = self._create_manual_alias_for_composition(
                composition_id=composition.composition_id,
                unresolved_text=raw_text,
            )
            if alias_warning:
                warnings.append(alias_warning)
                logger.warning(alias_warning)
        elif alias_text:
            alias_warning = self._create_manual_alias_for_composition(
                composition_id=composition.composition_id,
                unresolved_text=alias_text,
            )
            if alias_warning:
                warnings.append(alias_warning)
                logger.warning(alias_warning)

        return composition, warnings

    def suggest_components_from_text(self, raw_text: str) -> list[str]:
        return self._suggest_components_from_unresolved_text(raw_text)

    def create_manual_alias_for_composition(
        self,
        *,
        composition_id: str,
        source_text: str,
    ) -> str | None:
        return self._create_manual_alias_for_composition(
            composition_id=composition_id,
            unresolved_text=source_text,
        )

    def _create_manual_alias_for_composition(
        self,
        *,
        composition_id: str,
        unresolved_text: str,
    ) -> str | None:
        alias_text = str(unresolved_text or "").strip()
        alias_norm = normalize_menu_import_text(alias_text)
        if not alias_norm:
            return None

        existing = self._alias_repository.find_by_alias_norm(alias_norm)
        if any(item.composition_id == composition_id for item in existing):
            return None
        if any(item.composition_id != composition_id for item in existing):
            return (
                "alias conflict: normalized unresolved text already mapped to another composition"
            )

        create_composition_alias(
            alias_repository=self._alias_repository,
            alias_id=self._generate_alias_id(),
            composition_id=composition_id,
            alias_text=alias_text,
            source="manual",
            confidence=1.0,
            composition_repository=self._composition_repository,
        )
        return None

    def _generate_alias_id(self) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        existing_ids = {alias.alias_id for alias in self._alias_repository.list_all()}
        for _ in range(50):
            suffix = "".join(secrets.choice(alphabet) for _ in range(6))
            candidate = f"alias_{suffix}"
            if candidate not in existing_ids:
                return candidate
        raise ValueError("unable to generate unique alias_id")

    def _generate_composition_id(self) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        for _ in range(50):
            suffix = "".join(secrets.choice(alphabet) for _ in range(6))
            candidate = f"cmp_{suffix}"
            if self._composition_repository.get(candidate) is None:
                return candidate
        raise ValueError("unable to generate unique composition_id")

    @staticmethod
    def _slugify_component_name(value: str) -> str:
        raw = str(value or "").lower().strip()
        normalized = (
            raw.replace("å", "a")
            .replace("ä", "a")
            .replace("ö", "o")
        )
        cleaned = "".join(ch if (ch.isalnum() or ch == " ") else " " for ch in normalized)
        return "_".join(cleaned.split())

    def _generate_component_id(self, composition: Composition, component_name: str) -> str:
        base = self._slugify_component_name(component_name)
        if not base:
            alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
            base = "cmp_" + "".join(secrets.choice(alphabet) for _ in range(6))

        existing_ids = {item.component_id for item in composition.components}
        candidate = base
        suffix = 2
        while candidate in existing_ids:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _normalize_component_name(value: str) -> str:
        return " ".join(str(value or "").strip().split())

    def _generate_component_seed(self) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        for _ in range(50):
            suffix = "".join(secrets.choice(alphabet) for _ in range(6))
            candidate = f"comp_{suffix}"
            if self._component_service.get_component(candidate) is None:
                return candidate
        raise ValueError("unable to generate unique component_id")

    @staticmethod
    def _normalize_component_key(value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @staticmethod
    def _capitalize_first(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text[:1].upper() + text[1:]

    def _suggest_components_from_unresolved_text(self, unresolved_text: str) -> list[str]:
        text = str(unresolved_text or "").strip()
        if not text:
            return []

        # Keep user-facing suggestion text intact (including Swedish characters).
        # Normalization/transliteration is only applied later when generating component_id.
        parts = re.split(r"\s+(?:med|och|m)\s+", text, flags=re.IGNORECASE)
        suggestions: list[str] = []
        for part in parts:
            candidate = self._capitalize_first(part)
            if candidate:
                suggestions.append(candidate)
        return suggestions

