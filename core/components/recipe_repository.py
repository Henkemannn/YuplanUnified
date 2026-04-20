from __future__ import annotations

from .recipe_domain import Recipe, RecipeIngredientLine


class InMemoryRecipeRepository:
    def __init__(self) -> None:
        self._recipes: dict[str, Recipe] = {}

    def add_recipe(self, recipe: Recipe) -> None:
        if recipe.recipe_id in self._recipes:
            raise ValueError(f"recipe already exists: {recipe.recipe_id}")
        self._recipes[recipe.recipe_id] = recipe

    def get_recipe(self, recipe_id: str) -> Recipe | None:
        return self._recipes.get(recipe_id)

    def update_recipe(self, recipe: Recipe) -> None:
        if recipe.recipe_id not in self._recipes:
            raise ValueError(f"recipe not found: {recipe.recipe_id}")
        self._recipes[recipe.recipe_id] = recipe

    def list_recipes_for_component(self, component_id: str) -> list[Recipe]:
        return [recipe for recipe in self._recipes.values() if recipe.component_id == component_id]

    def delete_recipe(self, recipe_id: str) -> None:
        if recipe_id not in self._recipes:
            raise ValueError(f"recipe not found: {recipe_id}")
        del self._recipes[recipe_id]

    def set_default_recipe_for_component(self, component_id: str, recipe_id: str) -> Recipe:
        target = self._recipes.get(recipe_id)
        if target is None:
            raise ValueError(f"recipe not found: {recipe_id}")
        if target.component_id != component_id:
            raise ValueError(
                f"recipe {recipe_id} does not belong to component {component_id}"
            )

        for existing in self._recipes.values():
            if existing.component_id == component_id and existing.is_default:
                self._recipes[existing.recipe_id] = Recipe(
                    recipe_id=existing.recipe_id,
                    component_id=existing.component_id,
                    recipe_name=existing.recipe_name,
                    visibility=existing.visibility,
                    is_default=False,
                    yield_portions=existing.yield_portions,
                    notes=existing.notes,
                )

        updated_target = Recipe(
            recipe_id=target.recipe_id,
            component_id=target.component_id,
            recipe_name=target.recipe_name,
            visibility=target.visibility,
            is_default=True,
            yield_portions=target.yield_portions,
            notes=target.notes,
        )
        self._recipes[recipe_id] = updated_target
        return updated_target


class InMemoryRecipeIngredientLineRepository:
    def __init__(self) -> None:
        self._lines: dict[str, RecipeIngredientLine] = {}

    def add_ingredient_line(self, line: RecipeIngredientLine) -> None:
        if line.recipe_ingredient_line_id in self._lines:
            raise ValueError(
                f"recipe ingredient line already exists: {line.recipe_ingredient_line_id}"
            )
        self._lines[line.recipe_ingredient_line_id] = line

    def get_ingredient_line(self, recipe_ingredient_line_id: str) -> RecipeIngredientLine | None:
        return self._lines.get(recipe_ingredient_line_id)

    def update_ingredient_line(self, line: RecipeIngredientLine) -> None:
        if line.recipe_ingredient_line_id not in self._lines:
            raise ValueError(
                f"recipe ingredient line not found: {line.recipe_ingredient_line_id}"
            )
        self._lines[line.recipe_ingredient_line_id] = line

    def delete_ingredient_line(self, recipe_ingredient_line_id: str) -> None:
        if recipe_ingredient_line_id not in self._lines:
            raise ValueError(f"recipe ingredient line not found: {recipe_ingredient_line_id}")
        del self._lines[recipe_ingredient_line_id]

    def delete_ingredient_lines_for_recipe(self, recipe_id: str) -> None:
        to_delete = [
            line_id
            for line_id, line in self._lines.items()
            if line.recipe_id == recipe_id
        ]
        for line_id in to_delete:
            del self._lines[line_id]

    def list_ingredient_lines_for_recipe(self, recipe_id: str) -> list[RecipeIngredientLine]:
        lines = [line for line in self._lines.values() if line.recipe_id == recipe_id]
        return sorted(lines, key=lambda line: (line.sort_order, line.recipe_ingredient_line_id))
