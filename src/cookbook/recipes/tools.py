"""Recipe tools: list, get, create, update and delete."""

from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from cookbook.common.fields import DecimalNumber, Limit, Offset
from cookbook.common.mcp.errors import tool_errors
from cookbook.common.mcp.session import Sessions
from cookbook.recipes import service
from cookbook.recipes.schemas import (
    Minutes,
    RecipeIn,
    RecipeList,
    RecipeListParams,
    RecipeOut,
    RecipePatch,
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
CREATE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
UPDATE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)

DOCUMENT_RULES = """\
Macronutrients (kcal, protein_g, carbs_g, fat_g) are whole-recipe totals, \
not per serving; per-serving values and total time are computed. Each \
ingredient line has a name, and a quantity with a unit code from list_units \
(both, or neither for "to taste"). Reuse names from search_ingredients."""


class Deleted(BaseModel):
    id: int
    deleted: bool


def register(mcp: MCPServer, sessions: Sessions) -> None:
    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    async def list_recipes(
        q: str | None = None,
        max_total_time: Minutes | None = None,
        min_kcal_per_serving: DecimalNumber | None = None,
        max_kcal_per_serving: DecimalNumber | None = None,
        min_protein_per_serving: DecimalNumber | None = None,
        max_protein_per_serving: DecimalNumber | None = None,
        min_carbs_per_serving: DecimalNumber | None = None,
        max_carbs_per_serving: DecimalNumber | None = None,
        min_fat_per_serving: DecimalNumber | None = None,
        max_fat_per_serving: DecimalNumber | None = None,
        ingredients: list[str] | None = None,
        ingredient_match: Literal["all", "any"] = "all",
        sort: str = "name",
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> RecipeList:
        """Find recipes; returns summaries and the total number that match.

        Filters combine with AND. `q` matches part of the name,
        case-insensitively. `max_total_time` is in minutes, and a missing
        prep or cook time counts as 0. The min_/max_ bounds are per serving
        and inclusive. `ingredients` lists ingredient names: with
        `ingredient_match` "all" (the default) a recipe must contain every
        one, with "any" at least one.

        `sort` is one of name, created_at, total_time, kcal_per_serving,
        protein_per_serving, carbs_per_serving, fat_per_serving; prefix it
        with "-" for descending order. Use get_recipe for the full recipe.
        """
        params = RecipeListParams(
            q=q,
            max_total_time=max_total_time,
            min_kcal_per_serving=min_kcal_per_serving,
            max_kcal_per_serving=max_kcal_per_serving,
            min_protein_per_serving=min_protein_per_serving,
            max_protein_per_serving=max_protein_per_serving,
            min_carbs_per_serving=min_carbs_per_serving,
            max_carbs_per_serving=max_carbs_per_serving,
            min_fat_per_serving=min_fat_per_serving,
            max_fat_per_serving=max_fat_per_serving,
            ingredients=ingredients or [],
            ingredient_match=ingredient_match,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return await sessions.run(service.list_recipes, params)

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    async def get_recipe(recipe_id: int) -> RecipeOut:
        """Get a full recipe: steps, ingredient lines, totals, per-serving macros, times."""
        return await sessions.run(service.get, recipe_id)

    @mcp.tool(annotations=CREATE, description=f"Create a recipe.\n\n{DOCUMENT_RULES}")
    @tool_errors
    async def create_recipe(recipe: RecipeIn) -> RecipeOut:
        return await sessions.run(service.create, recipe)

    @mcp.tool(
        annotations=UPDATE,
        description=f"""\
Change a recipe: send only the fields to change in `changes`.

Fields left out stay as they are. `steps` and `ingredients` replace the \
whole list, so send every step or line you want to keep. null clears \
description, prep_time_min or cook_time_min; other fields can't be null. \
The result is checked as a whole recipe, and nothing is saved if it fails.

{DOCUMENT_RULES}""",
    )
    @tool_errors
    async def update_recipe(recipe_id: int, changes: RecipePatch) -> RecipeOut:
        return await sessions.run(service.update, recipe_id, changes)

    @mcp.tool(annotations=DELETE)
    @tool_errors
    async def delete_recipe(recipe_id: int) -> Deleted:
        """Delete a recipe with its steps and ingredient lines.

        Ingredients stay in the catalogue.
        """
        await sessions.run(service.delete, recipe_id)
        return Deleted(id=recipe_id, deleted=True)
