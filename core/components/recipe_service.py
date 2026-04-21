from __future__ import annotations

from decimal import Decimal

from .recipe_domain import Recipe, RecipeIngredientLine
from .recipe_repository import InMemoryRecipeIngredientLineRepository, InMemoryRecipeRepository

_ALLOWED_VISIBILITY = {"private", "site", "tenant"}
_KNOWN_TRAIT_SIGNALS = {"lactose", "gluten", "fish", "egg", "nuts"}


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

    def update_recipe_metadata(
        self,
        *,
        recipe_id: str,
        recipe_name: str,
        yield_portions: int,
        visibility: str | None = None,
        notes: str | None = None,
    ) -> Recipe:
        recipe = self._recipe_repository.get_recipe(recipe_id)
        if recipe is None:
            raise ValueError(f"recipe not found: {recipe_id}")

        recipe_name_value = str(recipe_name or "").strip()
        if not recipe_name_value:
            raise ValueError("recipe_name must be non-empty")

        yield_value = int(yield_portions)
        if yield_value <= 0:
            raise ValueError("yield_portions must be > 0")

        visibility_value = recipe.visibility
        if visibility is not None:
            visibility_value = str(visibility or "").strip().lower()
            if visibility_value not in _ALLOWED_VISIBILITY:
                raise ValueError(
                    "invalid visibility; expected one of: private, site, tenant"
                )

        updated = Recipe(
            recipe_id=recipe.recipe_id,
            component_id=recipe.component_id,
            recipe_name=recipe_name_value,
            visibility=visibility_value,
            is_default=recipe.is_default,
            yield_portions=yield_value,
            notes=notes,
        )
        self._recipe_repository.update_recipe(updated)
        return updated

    def list_recipes_for_component(self, component_id: str) -> list[Recipe]:
        return self._recipe_repository.list_recipes_for_component(component_id)

    def set_default_recipe(self, component_id: str, recipe_id: str) -> Recipe:
        return self._recipe_repository.set_default_recipe_for_component(component_id, recipe_id)

    def delete_recipe(self, recipe_id: str) -> None:
        recipe = self._recipe_repository.get_recipe(recipe_id)
        if recipe is None:
            raise ValueError(f"recipe not found: {recipe_id}")
        self._ingredient_line_repository.delete_ingredient_lines_for_recipe(recipe_id)
        self._recipe_repository.delete_recipe(recipe_id)

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
        trait_signals: list[str] | tuple[str, ...] | None = None,
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
            trait_signals=_normalize_trait_signals(trait_signals),
        )
        self._ingredient_line_repository.add_ingredient_line(line)
        return line

    def list_ingredient_lines(self, recipe_id: str) -> list[RecipeIngredientLine]:
        return self._ingredient_line_repository.list_ingredient_lines_for_recipe(recipe_id)

    def get_ingredient_line(self, recipe_ingredient_line_id: str) -> RecipeIngredientLine | None:
        return self._ingredient_line_repository.get_ingredient_line(recipe_ingredient_line_id)

    def update_ingredient_line(
        self,
        *,
        recipe_ingredient_line_id: str,
        ingredient_name: str,
        quantity_value: int | float | Decimal,
        quantity_unit: str,
        note: str | None = None,
        sort_order: int = 0,
        trait_signals: list[str] | tuple[str, ...] | None = None,
    ) -> RecipeIngredientLine:
        existing = self._ingredient_line_repository.get_ingredient_line(recipe_ingredient_line_id)
        if existing is None:
            raise ValueError(f"recipe ingredient line not found: {recipe_ingredient_line_id}")

        recipe = self._recipe_repository.get_recipe(existing.recipe_id)
        if recipe is None:
            raise ValueError(f"recipe not found: {existing.recipe_id}")

        ingredient_name_value = str(ingredient_name or "").strip()
        if not ingredient_name_value:
            raise ValueError("ingredient_name must be non-empty")

        quantity_decimal = _to_decimal(quantity_value, field_name="quantity_value")
        if quantity_decimal <= 0:
            raise ValueError("quantity_value must be > 0")

        quantity_unit_value = str(quantity_unit or "").strip()
        if not quantity_unit_value:
            raise ValueError("quantity_unit must be a non-empty explicit unit")

        updated = RecipeIngredientLine(
            recipe_ingredient_line_id=existing.recipe_ingredient_line_id,
            recipe_id=existing.recipe_id,
            ingredient_name=ingredient_name_value,
            quantity_value=quantity_decimal,
            quantity_unit=quantity_unit_value,
            unit_price_value=existing.unit_price_value,
            unit_price_unit=existing.unit_price_unit,
            note=note,
            sort_order=int(sort_order),
            trait_signals=(
                _normalize_trait_signals(trait_signals)
                if trait_signals is not None
                else existing.trait_signals
            ),
        )
        self._ingredient_line_repository.update_ingredient_line(updated)
        return updated

    def delete_ingredient_line(self, recipe_ingredient_line_id: str) -> None:
        existing = self._ingredient_line_repository.get_ingredient_line(recipe_ingredient_line_id)
        if existing is None:
            raise ValueError(f"recipe ingredient line not found: {recipe_ingredient_line_id}")
        self._ingredient_line_repository.delete_ingredient_line(recipe_ingredient_line_id)


def _to_decimal(value: int | float | Decimal, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive conversion guard
        raise ValueError(f"{field_name} must be numeric") from exc


def _normalize_trait_signals(
    trait_signals: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if trait_signals is None:
        return ()

    values: set[str] = set()
    for raw in trait_signals:
        value = str(raw or "").strip().lower()
        if not value:
            continue
        values.add(value)

    # Keep the baseline known signals first while allowing extension values.
    known = sorted(v for v in values if v in _KNOWN_TRAIT_SIGNALS)
    extension = sorted(v for v in values if v not in _KNOWN_TRAIT_SIGNALS)
    return tuple(known + extension)
