"""Recipe listing: filters, ingredient match, sorting and pagination."""

from __future__ import annotations

from sqlalchemy import ColumnElement, Select, exists, func, select
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient
from cookbook.recipes.models import Recipe, RecipeIngredient
from cookbook.recipes.schemas import RecipeList, RecipeListParams, RecipeSummary

# Missing times count as zero for filtering and sorting.
_TOTAL_TIME = func.coalesce(Recipe.total_time_min, 0)

_PER_SERVING = {
    "kcal": Recipe.kcal_per_serving,
    "protein": Recipe.protein_g_per_serving,
    "carbs": Recipe.carbs_g_per_serving,
    "fat": Recipe.fat_g_per_serving,
}

_SORT_COLUMNS: dict[str, ColumnElement] = {
    "name": Recipe.name,
    "created_at": Recipe.created_at,
    "total_time": _TOTAL_TIME,
    **{f"{macro}_per_serving": col for macro, col in _PER_SERVING.items()},
}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _ingredient_filter(names: list[str], match: str) -> ColumnElement[bool]:
    """``names`` are already normalized and distinct."""
    if match == "any":
        return exists(
            select(RecipeIngredient.id)
            .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
            .where(RecipeIngredient.recipe_id == Recipe.id, Ingredient.name.in_(names))
        )
    having_all = (
        select(RecipeIngredient.recipe_id)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(Ingredient.name.in_(names))
        .group_by(RecipeIngredient.recipe_id)
        .having(func.count(func.distinct(RecipeIngredient.ingredient_id)) == len(names))
    )
    return Recipe.id.in_(having_all)


def _filtered(params: RecipeListParams) -> Select:
    stmt = select(Recipe)
    q = (params.q or "").strip()
    if q:
        stmt = stmt.where(Recipe.name.ilike(f"%{_escape_like(q)}%", escape="\\"))
    if params.max_total_time is not None:
        stmt = stmt.where(params.max_total_time >= _TOTAL_TIME)
    for macro, column in _PER_SERVING.items():
        low = getattr(params, f"min_{macro}_per_serving")
        high = getattr(params, f"max_{macro}_per_serving")
        if low is not None:
            stmt = stmt.where(column >= low)
        if high is not None:
            stmt = stmt.where(column <= high)
    if params.ingredient:
        stmt = stmt.where(_ingredient_filter(params.ingredient, params.ingredient_match))
    return stmt


def _summary(recipe: Recipe) -> RecipeSummary:
    return RecipeSummary(
        id=recipe.id,
        name=recipe.name,
        servings=recipe.servings,
        prep_time_min=recipe.prep_time_min,
        cook_time_min=recipe.cook_time_min,
        total_time_min=recipe.total_time_min,
        kcal_per_serving=recipe.kcal_per_serving,
        protein_per_serving=recipe.protein_g_per_serving,
        carbs_per_serving=recipe.carbs_g_per_serving,
        fat_per_serving=recipe.fat_g_per_serving,
    )


def list_recipes(session: Session, params: RecipeListParams) -> RecipeList:
    stmt = _filtered(params)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    key = params.sort.removeprefix("-")
    column = _SORT_COLUMNS[key]
    order = column.desc() if params.sort.startswith("-") else column.asc()
    page = stmt.order_by(order, Recipe.id).limit(params.limit).offset(params.offset)

    return RecipeList(
        items=[_summary(r) for r in session.scalars(page)],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )
