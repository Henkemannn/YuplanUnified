from __future__ import annotations

from dataclasses import dataclass, field
import logging

from .builder import BuilderFlow
from .components import (
    Composition,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from .menu import (
    ImportedMenuRow,
    InMemoryCompositionAliasRepository,
    MenuDetail,
    MenuDetailCostBreakdown,
    MenuImportSummary,
    MenuService,
    calculate_menu_detail_cost,
    import_menu_rows,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MenuCostOverview:
    menu_id: str
    detail_costs: list[MenuDetailCostBreakdown] = field(default_factory=list)
    unresolved_count: int = 0
    warnings: list[str] = field(default_factory=list)


class BuilderMenuContextFlow:
    _DAY_ORDER = {
        "monday": 1,
        "tuesday": 2,
        "wednesday": 3,
        "thursday": 4,
        "friday": 5,
        "saturday": 6,
        "sunday": 7,
    }
    _MEAL_SLOT_ORDER = {
        "breakfast": 1,
        "lunch": 2,
        "dinner": 3,
        "kvallsmat": 4,
    }

    def __init__(
        self,
        *,
        menu_service: MenuService,
        composition_repository: InMemoryCompositionRepository,
        alias_repository: InMemoryCompositionAliasRepository,
        recipe_repository: InMemoryRecipeRepository,
        ingredient_repository: InMemoryRecipeIngredientLineRepository,
        library_flow: BuilderFlow,
    ) -> None:
        self._menu_service = menu_service
        self._composition_repository = composition_repository
        self._alias_repository = alias_repository
        self._recipe_repository = recipe_repository
        self._ingredient_repository = ingredient_repository
        self._library_flow = library_flow

    def create_menu(
        self,
        menu_id: str,
        site_id: str,
        week_key: str,
        *,
        title: str | None = None,
        version: int = 1,
        status: str = "draft",
    ):
        return self._menu_service.create_menu(
            menu_id=menu_id,
            title=title,
            site_id=site_id,
            week_key=week_key,
            version=version,
            status=status,
        )

    def list_menus(self):
        return self._menu_service.list_menus()

    def add_composition_menu_row(
        self,
        *,
        menu_id: str,
        day: str,
        meal_slot: str,
        composition_id: str,
        note: str | None = None,
        sort_order: int = 0,
        menu_detail_id: str | None = None,
    ) -> MenuDetail:
        detail_id = str(menu_detail_id or "").strip()
        if not detail_id:
            existing = self._menu_service.list_menu_details(menu_id)
            detail_id = f"{menu_id}-row-{len(existing) + 1}"
        return self._menu_service.add_menu_detail(
            menu_detail_id=detail_id,
            menu_id=menu_id,
            day=day,
            meal_slot=meal_slot,
            composition_ref_type="composition",
            composition_id=composition_id,
            unresolved_text=None,
            note=note,
            sort_order=sort_order,
        )

    def update_composition_menu_row(
        self,
        *,
        menu_id: str,
        menu_detail_id: str,
        day: str,
        meal_slot: str,
        composition_id: str,
        note: str | None = None,
        sort_order: int | None = None,
    ) -> MenuDetail:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")

        return self._menu_service.update_menu_detail(
            menu_detail_id=menu_detail_id,
            day=day,
            meal_slot=meal_slot,
            composition_ref_type="composition",
            composition_id=composition_id,
            unresolved_text="",
            note=note,
            sort_order=sort_order,
        )

    def delete_menu_row(self, *, menu_id: str, menu_detail_id: str) -> None:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")
        self._menu_service.remove_menu_detail(menu_detail_id)

    def list_menu_rows(self, menu_id: str) -> list[dict[str, str | int | None]]:
        rows: list[dict[str, str | int | None]] = []
        for detail in self._menu_service.list_menu_details(menu_id):
            composition_name: str | None = None
            if detail.composition_id:
                composition = self._composition_repository.get(detail.composition_id)
                if composition is not None:
                    composition_name = composition.composition_name
            rows.append(
                {
                    "menu_detail_id": detail.menu_detail_id,
                    "menu_id": detail.menu_id,
                    "day": detail.day,
                    "meal_slot": detail.meal_slot,
                    "composition_ref_type": detail.composition_ref_type,
                    "composition_id": detail.composition_id,
                    "composition_name": composition_name,
                    "unresolved_text": detail.unresolved_text,
                    "note": detail.note,
                    "sort_order": detail.sort_order,
                }
            )
        return sorted(
            rows,
            key=lambda row: (
                int(row.get("sort_order") or 0),
                str(row.get("day") or ""),
                str(row.get("meal_slot") or ""),
                str(row.get("menu_detail_id") or ""),
            ),
        )

    def list_menu_rows_grouped(
        self,
        menu_id: str,
    ) -> list[dict[str, str | int | list[dict[str, str | int | None]]]]:
        rows = self.list_menu_rows(menu_id)
        grouped: dict[tuple[str, str], list[dict[str, str | int | None]]] = {}

        for row in rows:
            day = str(row.get("day") or "")
            meal_slot = str(row.get("meal_slot") or "")
            key = (day, meal_slot)
            grouped.setdefault(key, []).append(row)

        groups: list[dict[str, str | int | list[dict[str, str | int | None]]]] = []
        for (day, meal_slot), grouped_rows in grouped.items():
            groups.append(
                {
                    "day": day,
                    "meal_slot": meal_slot,
                    "count": len(grouped_rows),
                    "rows": grouped_rows,
                }
            )

        return sorted(
            groups,
            key=lambda group: (
                self._DAY_ORDER.get(str(group.get("day") or ""), 99),
                self._MEAL_SLOT_ORDER.get(str(group.get("meal_slot") or ""), 99),
                str(group.get("day") or ""),
                str(group.get("meal_slot") or ""),
            ),
        )

    def import_menu_rows(self, menu_id: str, rows: list[ImportedMenuRow]) -> MenuImportSummary:
        return import_menu_rows(
            menu_id=menu_id,
            rows=rows,
            menu_service=self._menu_service,
            composition_repository=self._composition_repository,
            alias_repository=self._alias_repository,
        )

    def list_unresolved_menu_details(self, menu_id: str) -> list[MenuDetail]:
        details = self._menu_service.list_menu_details(menu_id)
        return [detail for detail in details if detail.composition_ref_type == "unresolved"]

    def resolve_menu_detail(
        self,
        menu_id: str,
        menu_detail_id: str,
        composition_id: str,
    ) -> MenuDetail:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")

        return self._menu_service.update_menu_detail(
            menu_detail_id=menu_detail_id,
            composition_ref_type="composition",
            composition_id=composition_id,
            unresolved_text="",
        )

    def create_composition_from_unresolved_row(
        self,
        menu_id: str,
        menu_detail_id: str,
        composition_name: str,
    ) -> tuple[Composition, MenuDetail, list[str]]:
        details = self._menu_service.list_menu_details(menu_id)
        match = next((detail for detail in details if detail.menu_detail_id == menu_detail_id), None)
        if match is None:
            raise ValueError("menu_detail_id not found for menu")
        if match.composition_ref_type != "unresolved":
            raise ValueError("menu detail must be unresolved")
        unresolved_text = str(match.unresolved_text or "").strip()
        if not unresolved_text:
            raise ValueError("unresolved row required")

        composition = self._library_flow.create_composition_with_generated_id(composition_name=composition_name)

        for suggestion in self._library_flow.suggest_components_from_text(unresolved_text):
            composition = self._library_flow.add_component_to_composition(
                composition_id=composition.composition_id,
                component_name=suggestion,
                role="component",
            )

        warnings: list[str] = []
        alias_warning = self._library_flow.create_manual_alias_for_composition(
            composition_id=composition.composition_id,
            source_text=unresolved_text,
        )
        if alias_warning:
            warnings.append(alias_warning)
            logger.warning(alias_warning)

        updated = self.resolve_menu_detail(
            menu_id=menu_id,
            menu_detail_id=menu_detail_id,
            composition_id=composition.composition_id,
        )
        return composition, updated, warnings

    def get_menu_cost_overview(
        self,
        menu_id: str,
        *,
        default_target_portions: int = 1,
        target_portions_by_detail: dict[str, int] | None = None,
    ) -> MenuCostOverview:
        details = self._menu_service.list_menu_details(menu_id)
        detail_costs: list[MenuDetailCostBreakdown] = []
        warnings: list[str] = []
        unresolved_count = 0

        targets = target_portions_by_detail or {}
        for detail in details:
            target_portions = int(targets.get(detail.menu_detail_id, default_target_portions))
            breakdown = calculate_menu_detail_cost(
                menu_detail=detail,
                composition_repository=self._composition_repository,
                recipe_repository=self._recipe_repository,
                ingredient_repository=self._ingredient_repository,
                target_portions=target_portions,
            )
            detail_costs.append(breakdown)
            if detail.composition_ref_type == "unresolved":
                unresolved_count += 1
            warnings.extend(breakdown.warnings)

        if unresolved_count > 0:
            warnings.append("menu contains unresolved details")

        return MenuCostOverview(
            menu_id=menu_id,
            detail_costs=detail_costs,
            unresolved_count=unresolved_count,
            warnings=warnings,
        )
