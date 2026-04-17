from __future__ import annotations

from dataclasses import dataclass, field

from ..components.composition_repository import InMemoryCompositionRepository
from .alias_repository import InMemoryCompositionAliasRepository
from .composition_resolution import resolve_composition_reference
from .menu_service import MenuService


@dataclass(frozen=True)
class ImportedMenuRow:
    day: str
    meal_slot: str
    raw_text: str
    note: str | None = None
    sort_order: int = 0


@dataclass(frozen=True)
class ImportedMenuRowResult:
    day: str
    meal_slot: str
    raw_text: str
    menu_detail_id: str | None
    kind: str
    composition_id: str | None
    unresolved_text: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MenuImportSummary:
    menu_id: str
    imported_count: int
    resolved_count: int
    unresolved_count: int
    row_results: list[ImportedMenuRowResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def import_menu_rows(
    menu_id: str,
    rows: list[ImportedMenuRow],
    menu_service: MenuService,
    composition_repository: InMemoryCompositionRepository,
    alias_repository: InMemoryCompositionAliasRepository,
) -> MenuImportSummary:
    existing_count = len(menu_service.list_menu_details(menu_id))

    row_results: list[ImportedMenuRowResult] = []
    resolved_count = 0
    unresolved_count = 0

    for index, row in enumerate(rows, start=1):
        menu_detail_id = f"{menu_id}-import-{existing_count + index}"

        resolution = resolve_composition_reference(
            import_text=row.raw_text,
            composition_repository=composition_repository,
            alias_repository=alias_repository,
        )

        warnings = list(resolution.warnings)
        if resolution.kind == "composition" and resolution.composition_id is not None:
            # Defensive check to avoid silently creating broken references if alias data is stale.
            if composition_repository.get(resolution.composition_id) is not None:
                detail = menu_service.add_menu_detail(
                    menu_detail_id=menu_detail_id,
                    menu_id=menu_id,
                    day=row.day,
                    meal_slot=row.meal_slot,
                    composition_ref_type="composition",
                    composition_id=resolution.composition_id,
                    note=row.note,
                    sort_order=row.sort_order,
                )
                resolved_count += 1
                row_results.append(
                    ImportedMenuRowResult(
                        day=row.day,
                        meal_slot=row.meal_slot,
                        raw_text=row.raw_text,
                        menu_detail_id=detail.menu_detail_id,
                        kind="composition",
                        composition_id=detail.composition_id,
                        unresolved_text=None,
                        warnings=warnings,
                    )
                )
                continue

            warnings.append("resolved composition missing; stored as unresolved")

        detail = menu_service.add_menu_detail(
            menu_detail_id=menu_detail_id,
            menu_id=menu_id,
            day=row.day,
            meal_slot=row.meal_slot,
            composition_ref_type="unresolved",
            unresolved_text=row.raw_text,
            note=row.note,
            sort_order=row.sort_order,
        )
        unresolved_count += 1
        row_results.append(
            ImportedMenuRowResult(
                day=row.day,
                meal_slot=row.meal_slot,
                raw_text=row.raw_text,
                menu_detail_id=detail.menu_detail_id,
                kind="unresolved",
                composition_id=None,
                unresolved_text=detail.unresolved_text,
                warnings=warnings,
            )
        )

    warnings: list[str] = []
    if unresolved_count > 0:
        warnings.append("one or more imported rows are unresolved")

    return MenuImportSummary(
        menu_id=menu_id,
        imported_count=len(row_results),
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
        row_results=row_results,
        warnings=warnings,
    )
