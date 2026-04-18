from __future__ import annotations

from dataclasses import dataclass, field

from ..components import (
    Composition,
    CompositionService,
    InMemoryCompositionRepository,
    InMemoryRecipeIngredientLineRepository,
    InMemoryRecipeRepository,
)
from ..menu import (
    ImportedMenuRow,
    InMemoryCompositionAliasRepository,
    MenuDetail,
    MenuDetailCostBreakdown,
    MenuImportSummary,
    MenuService,
    calculate_menu_detail_cost,
    import_menu_rows,
)


@dataclass(frozen=True)
class MenuCostOverview:
    menu_id: str
    detail_costs: list[MenuDetailCostBreakdown] = field(default_factory=list)
    unresolved_count: int = 0
    warnings: list[str] = field(default_factory=list)


class BuilderFlow:
    def __init__(
        self,
        *,
        composition_service: CompositionService,
        menu_service: MenuService,
        composition_repository: InMemoryCompositionRepository,
        alias_repository: InMemoryCompositionAliasRepository,
        recipe_repository: InMemoryRecipeRepository,
        ingredient_repository: InMemoryRecipeIngredientLineRepository,
    ) -> None:
        self._composition_service = composition_service
        self._menu_service = menu_service
        self._composition_repository = composition_repository
        self._alias_repository = alias_repository
        self._recipe_repository = recipe_repository
        self._ingredient_repository = ingredient_repository

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

    def add_component_to_composition(
        self,
        composition_id: str,
        component_id: str,
        *,
        role: str | None = None,
        sort_order: int | None = None,
    ) -> Composition:
        return self._composition_service.add_component_to_composition(
            composition_id=composition_id,
            component_id=component_id,
            role=role,
            sort_order=sort_order,
        )

    def create_menu(
        self,
        menu_id: str,
        site_id: str,
        week_key: str,
        *,
        version: int = 1,
        status: str = "draft",
    ):
        return self._menu_service.create_menu(
            menu_id=menu_id,
            site_id=site_id,
            week_key=week_key,
            version=version,
            status=status,
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
            unresolved_text=None,
        )

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
