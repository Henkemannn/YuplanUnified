from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .composition_domain import Composition
from .recipe_calculations import calculate_recipe_cost_breakdown
from .recipe_domain import Recipe
from .recipe_repository import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository


@dataclass(frozen=True)
class ComponentCostBreakdown:
    component_id: str
    recipe_id: str | None
    scaled_cost: Decimal | None
    cost_per_portion: Decimal | None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompositionCostBreakdown:
    composition_id: str
    target_portions: int
    component_breakdowns: list[ComponentCostBreakdown] = field(default_factory=list)
    total_cost: Decimal | None = None
    cost_per_portion: Decimal | None = None
    warnings: list[str] = field(default_factory=list)


def calculate_composition_cost(
    composition: Composition,
    recipe_repository: InMemoryRecipeRepository,
    ingredient_repository: InMemoryRecipeIngredientLineRepository,
    target_portions: int,
) -> CompositionCostBreakdown:
    if int(target_portions) <= 0:
        raise ValueError("target_portions must be > 0")

    component_breakdowns: list[ComponentCostBreakdown] = []
    warnings: list[str] = []

    total_known_cost = Decimal("0")
    missing_component_cost = False

    for component in composition.components:
        default_recipe = _get_default_recipe_for_component(recipe_repository, component.component_id)
        if default_recipe is None:
            warning = f"missing default recipe for component: {component.component_id}"
            warnings.append(warning)
            missing_component_cost = True
            component_breakdowns.append(
                ComponentCostBreakdown(
                    component_id=component.component_id,
                    recipe_id=None,
                    scaled_cost=None,
                    cost_per_portion=None,
                    warnings=[warning],
                )
            )
            continue

        ingredient_lines = ingredient_repository.list_ingredient_lines_for_recipe(
            default_recipe.recipe_id
        )
        recipe_breakdown = calculate_recipe_cost_breakdown(
            recipe=default_recipe,
            ingredient_lines=ingredient_lines,
            target_portions=target_portions,
        )

        component_warnings = list(recipe_breakdown.warnings)
        if component_warnings:
            for message in component_warnings:
                warnings.append(f"component {component.component_id}: {message}")

        if recipe_breakdown.total_cost is None:
            missing_component_cost = True
        else:
            total_known_cost += recipe_breakdown.total_cost

        component_breakdowns.append(
            ComponentCostBreakdown(
                component_id=component.component_id,
                recipe_id=default_recipe.recipe_id,
                scaled_cost=recipe_breakdown.total_cost,
                cost_per_portion=recipe_breakdown.cost_per_portion,
                warnings=component_warnings,
            )
        )

    total_cost: Decimal | None = None if missing_component_cost else total_known_cost
    cost_per_portion = (
        (total_cost / Decimal(target_portions)) if total_cost is not None else None
    )

    return CompositionCostBreakdown(
        composition_id=composition.composition_id,
        target_portions=int(target_portions),
        component_breakdowns=component_breakdowns,
        total_cost=total_cost,
        cost_per_portion=cost_per_portion,
        warnings=warnings,
    )


def _get_default_recipe_for_component(
    recipe_repository: InMemoryRecipeRepository,
    component_id: str,
) -> Recipe | None:
    recipes = recipe_repository.list_recipes_for_component(component_id)
    for recipe in recipes:
        if recipe.is_default:
            return recipe
    return None
