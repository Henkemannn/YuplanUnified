from __future__ import annotations

from decimal import Decimal

from .recipe_domain import Recipe, RecipeIngredientLine
from .recipe_repository import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository

_ALLOWED_VISIBILITY = {"private", "site", "tenant"}


class RecipeService:
    def __init__(
        self,
        recipe_repository: InMemoryRecipeRepository | None = None,
        ingredient_line_repository: InMemoryRecipeIngredientLineRepository | None = None,
    ) -> None:
        self._recipe_repository = recipe_repository or InMemoryRecipeRepository()
        self._ingredient_line_repository = (
            ingredient_line_repository or InMemoryRecipeIngredientLineRepository()
        )

    def create_recipe(
        self,
        recipe_id: str,
        component_id: str,
        recipe_name: str,
        visibility: str,
        yield_portions: int,
        *,
        is_default: bool = False,
        notes: str | None = None,
    ) -> Recipe:
        visibility_value = str(visibility or "").strip().lower()
        if visibility_value not in _ALLOWED_VISIBILITY:
            raise ValueError(
                "invalid visibility; expected one of: private, site, tenant"
            )

        if int(yield_portions) <= 0:
            raise ValueError("yield_portions must be > 0")

        recipe = Recipe(
            recipe_id=str(recipe_id).strip(),
            component_id=str(component_id).strip(),
            recipe_name=str(recipe_name).strip(),
            visibility=visibility_value,
            is_default=bool(is_default),
            yield_portions=int(yield_portions),
            notes=notes,
        )
        self._recipe_repository.add_recipe(recipe)
        if recipe.is_default:
            return self._recipe_repository.set_default_recipe_for_component(
                component_id=recipe.component_id,
                recipe_id=recipe.recipe_id,
            )
        return recipe

    def get_recipe(self, recipe_id: str) -> Recipe | None:
        return self._recipe_repository.get_recipe(recipe_id)

    def list_recipes_for_component(self, component_id: str) -> list[Recipe]:
        return self._recipe_repository.list_recipes_for_component(component_id)

    def set_default_recipe(self, component_id: str, recipe_id: str) -> Recipe:
        return self._recipe_repository.set_default_recipe_for_component(component_id, recipe_id)

    def add_ingredient_line(
        self,
        recipe_ingredient_line_id: str,
        recipe_id: str,
        ingredient_name: str,
        quantity_value: int | float | Decimal,
        quantity_unit: str,
        *,
        unit_price_value: int | float | Decimal | None = None,
        unit_price_unit: str | None = None,
        note: str | None = None,
        sort_order: int = 0,
    ) -> RecipeIngredientLine:
        recipe = self._recipe_repository.get_recipe(recipe_id)
        if recipe is None:
            raise ValueError(f"recipe not found: {recipe_id}")

        quantity_decimal = _to_decimal(quantity_value, field_name="quantity_value")
        if quantity_decimal <= 0:
            raise ValueError("quantity_value must be > 0")

        quantity_unit_value = str(quantity_unit or "").strip()
        if not quantity_unit_value:
            raise ValueError("quantity_unit must be a non-empty explicit unit")

        unit_price_decimal: Decimal | None = None
        if unit_price_value is not None:
            unit_price_decimal = _to_decimal(unit_price_value, field_name="unit_price_value")

        line = RecipeIngredientLine(
            recipe_ingredient_line_id=str(recipe_ingredient_line_id).strip(),
            recipe_id=recipe.recipe_id,
            ingredient_name=str(ingredient_name).strip(),
            quantity_value=quantity_decimal,
            quantity_unit=quantity_unit_value,
            unit_price_value=unit_price_decimal,
            unit_price_unit=str(unit_price_unit).strip() if unit_price_unit is not None else None,
            note=note,
            sort_order=int(sort_order),
        )
        self._ingredient_line_repository.add_ingredient_line(line)
        return line

    def list_ingredient_lines(self, recipe_id: str) -> list[RecipeIngredientLine]:
        return self._ingredient_line_repository.list_ingredient_lines_for_recipe(recipe_id)


def _to_decimal(value: int | float | Decimal, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive conversion guard
        raise ValueError(f"{field_name} must be numeric") from exc
