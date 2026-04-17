from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..components.composition_cost import CompositionCostBreakdown, calculate_composition_cost
from ..components.composition_repository import InMemoryCompositionRepository
from ..components.recipe_repository import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository
from .menu_domain import MenuDetail


@dataclass(frozen=True)
class MenuDetailCostBreakdown:
    menu_detail_id: str
    menu_id: str
    composition_id: str | None
    target_portions: int
    total_cost: Decimal | None
    cost_per_portion: Decimal | None
    warnings: list[str] = field(default_factory=list)
    composition_breakdown: CompositionCostBreakdown | None = None


def calculate_menu_detail_cost(
    menu_detail: MenuDetail,
    composition_repository: InMemoryCompositionRepository,
    recipe_repository: InMemoryRecipeRepository,
    ingredient_repository: InMemoryRecipeIngredientLineRepository,
    target_portions: int,
) -> MenuDetailCostBreakdown:
    if int(target_portions) <= 0:
        raise ValueError("target_portions must be > 0")

    ref_type = str(menu_detail.composition_ref_type or "").strip().lower()

    if ref_type == "unresolved":
        return MenuDetailCostBreakdown(
            menu_detail_id=menu_detail.menu_detail_id,
            menu_id=menu_detail.menu_id,
            composition_id=None,
            target_portions=int(target_portions),
            total_cost=None,
            cost_per_portion=None,
            warnings=["menu detail unresolved; composition cost unavailable"],
            composition_breakdown=None,
        )

    composition_id = str(menu_detail.composition_id or "").strip()
    composition = composition_repository.get(composition_id) if composition_id else None
    if ref_type != "composition" or composition is None:
        return MenuDetailCostBreakdown(
            menu_detail_id=menu_detail.menu_detail_id,
            menu_id=menu_detail.menu_id,
            composition_id=composition_id or None,
            target_portions=int(target_portions),
            total_cost=None,
            cost_per_portion=None,
            warnings=["composition not found for menu detail"],
            composition_breakdown=None,
        )

    composition_breakdown = calculate_composition_cost(
        composition=composition,
        recipe_repository=recipe_repository,
        ingredient_repository=ingredient_repository,
        target_portions=int(target_portions),
    )

    return MenuDetailCostBreakdown(
        menu_detail_id=menu_detail.menu_detail_id,
        menu_id=menu_detail.menu_id,
        composition_id=composition.composition_id,
        target_portions=int(target_portions),
        total_cost=composition_breakdown.total_cost,
        cost_per_portion=composition_breakdown.cost_per_portion,
        warnings=list(composition_breakdown.warnings),
        composition_breakdown=composition_breakdown,
    )
