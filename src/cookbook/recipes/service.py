"""Recipe reads, listing and writes. Each write is one transaction, committed here."""

from __future__ import annotations

from sqlalchemy import ColumnElement, Select, exists, func, select
from sqlalchemy import delete as sql_delete
from sqlalchemy.orm import Session, selectinload

from cookbook.common.errors import InvalidInputError, NotFoundError
from cookbook.ingredients import service as ingredients
from cookbook.ingredients.models import Ingredient
from cookbook.recipes.models import Recipe, RecipeIngredient, RecipeStep
from cookbook.recipes.schemas import (
    IngredientLineOut,
    RecipeIn,
    RecipeList,
    RecipeListParams,
    RecipeOut,
    RecipePatch,
    RecipeSummary,
)
from cookbook.units import service as units

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


def get(session: Session, recipe_id: int) -> RecipeOut:
    return _to_out(_load(session, recipe_id))


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
        unmatched_ingredients=_unmatched(
            session, list(dict.fromkeys(params.all_ingredients + params.any_ingredients))
        ),
    )


def create(session: Session, doc: RecipeIn) -> RecipeOut:
    try:
        _check_units(session, doc)
        recipe = Recipe()
        _apply(session, recipe, doc)
        session.add(recipe)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return get(session, recipe.id)


def update(session: Session, recipe_id: int, patch: RecipePatch) -> RecipeOut:
    """Merge ``patch`` into the stored recipe and store it atomically.

    The merged document is validated as a whole ``RecipeIn``, so rules that
    span fields (quantity needs a unit) and unit checks apply to the result.
    Lists in the patch replace the stored lists.
    """
    merged = _as_document(get(session, recipe_id)) | patch.model_dump(exclude_unset=True)
    return _replace(session, recipe_id, RecipeIn.model_validate(merged))


def delete(session: Session, recipe_id: int) -> None:
    """Delete a recipe with its steps and lines; catalogue ingredients stay."""
    try:
        recipe = session.get(Recipe, recipe_id)
        if recipe is None:
            raise NotFoundError(f"recipe {recipe_id} not found")
        session.delete(recipe)
        session.commit()
    except Exception:
        session.rollback()
        raise


def _load(session: Session, recipe_id: int) -> Recipe:
    recipe = session.scalar(
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .options(
            selectinload(Recipe.steps),
            selectinload(Recipe.lines).joinedload(RecipeIngredient.ingredient),
        )
        .execution_options(populate_existing=True)
    )
    if recipe is None:
        raise NotFoundError(f"recipe {recipe_id} not found")
    return recipe


def _to_out(recipe: Recipe) -> RecipeOut:
    return RecipeOut(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        servings=recipe.servings,
        prep_time_min=recipe.prep_time_min,
        cook_time_min=recipe.cook_time_min,
        total_time_min=recipe.total_time_min,
        kcal=recipe.kcal,
        protein_g=recipe.protein_g,
        carbs_g=recipe.carbs_g,
        fat_g=recipe.fat_g,
        kcal_per_serving=recipe.kcal_per_serving,
        protein_per_serving=recipe.protein_g_per_serving,
        carbs_per_serving=recipe.carbs_g_per_serving,
        fat_per_serving=recipe.fat_g_per_serving,
        steps=[s.text for s in recipe.steps],
        ingredients=[
            IngredientLineOut(
                ingredient_id=line.ingredient_id,
                name=line.ingredient.name,
                quantity=line.quantity,
                unit=line.unit,
                prep_note=line.prep_note,
                optional=line.optional,
            )
            for line in recipe.lines
        ],
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )


def _as_document(recipe: RecipeOut) -> dict[str, object]:
    """The stored recipe in ``RecipeIn`` shape, without derived or server fields."""
    return {
        **recipe.model_dump(include=set(RecipeIn.model_fields) - {"ingredients"}),
        "ingredients": [
            line.model_dump(include={"name", "quantity", "unit", "prep_note", "optional"})
            for line in recipe.ingredients
        ],
    }


def _replace(session: Session, recipe_id: int, doc: RecipeIn) -> RecipeOut:
    """Replace the whole recipe, steps and lines included, atomically."""
    try:
        recipe = session.get(Recipe, recipe_id)
        if recipe is None:
            raise NotFoundError(f"recipe {recipe_id} not found")
        _check_units(session, doc)
        # Delete old children up front: the unit of work inserts before it
        # deletes, which would collide on (recipe_id, position).
        session.execute(sql_delete(RecipeStep).where(RecipeStep.recipe_id == recipe_id))
        session.execute(sql_delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id))
        session.expire(recipe, ["steps", "lines"])
        _apply(session, recipe, doc)
        # onupdate only fires when a recipes column changed; children count too.
        recipe.updated_at = func.now()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return get(session, recipe_id)


def _check_units(session: Session, doc: RecipeIn) -> None:
    """Reject unknown unit codes with a validation error that names them.

    The FK on recipe_ingredients.unit would catch these too, but only as an
    IntegrityError that doesn't say which code was wrong.
    """
    unknown = set(units.unknown_codes(session, (ln.unit for ln in doc.ingredients if ln.unit)))
    if not unknown:
        return
    details = [
        {
            "loc": ["ingredients", i, "unit"],
            "msg": f"unknown unit {line.unit!r}",
            "type": "unknown_unit",
        }
        for i, line in enumerate(doc.ingredients)
        if line.unit in unknown
    ]
    raise InvalidInputError("unknown unit code: " + ", ".join(sorted(unknown)), details)


def _apply(session: Session, recipe: Recipe, doc: RecipeIn) -> None:
    """Copy ``doc`` onto ``recipe``, replacing all steps and ingredient lines."""
    ingredient_ids = ingredients.get_or_create(session, (ln.name for ln in doc.ingredients))

    recipe.name = doc.name
    recipe.description = doc.description
    recipe.servings = doc.servings
    recipe.prep_time_min = doc.prep_time_min
    recipe.cook_time_min = doc.cook_time_min
    recipe.kcal = doc.kcal
    recipe.protein_g = doc.protein_g
    recipe.carbs_g = doc.carbs_g
    recipe.fat_g = doc.fat_g

    recipe.steps = [RecipeStep(position=i, text=text) for i, text in enumerate(doc.steps)]
    recipe.lines = [
        RecipeIngredient(
            position=i,
            ingredient_id=ingredient_ids[line.name],
            quantity=line.quantity,
            unit=line.unit,
            prep_note=line.prep_note,
            optional=line.optional,
        )
        for i, line in enumerate(doc.ingredients)
    ]


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
    if params.all_ingredients:
        stmt = stmt.where(_contains_all(params.all_ingredients))
    if params.any_ingredients:
        stmt = stmt.where(_contains_any(params.any_ingredients))
    return stmt


def _contains_all(names: list[str]) -> ColumnElement[bool]:
    """``names`` are already normalized and distinct."""
    having_all = (
        select(RecipeIngredient.recipe_id)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(Ingredient.name.in_(names))
        .group_by(RecipeIngredient.recipe_id)
        .having(func.count(func.distinct(RecipeIngredient.ingredient_id)) == len(names))
    )
    return Recipe.id.in_(having_all)


def _contains_any(names: list[str]) -> ColumnElement[bool]:
    return exists(
        select(RecipeIngredient.id)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id == Recipe.id, Ingredient.name.in_(names))
    )


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


def _unmatched(session: Session, names: list[str]) -> list[str]:
    """The ``names`` not in the ingredient catalogue, in the given order."""
    if not names:
        return []
    known = set(session.scalars(select(Ingredient.name).where(Ingredient.name.in_(names))))
    return [name for name in names if name not in known]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
