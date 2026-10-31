"""Recipe reads and writes. Each write is one transaction, committed here."""

from __future__ import annotations

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from cookbook.common.errors import InvalidInputError, NotFoundError
from cookbook.ingredients import service as ingredients
from cookbook.recipes.models import Recipe, RecipeIngredient, RecipeStep
from cookbook.recipes.schemas import IngredientLineOut, RecipeIn, RecipeOut
from cookbook.units import service as units


def _check_units(session: Session, doc: RecipeIn) -> None:
    """Reject unknown unit codes with a 422 that names them.

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


def get(session: Session, recipe_id: int) -> RecipeOut:
    return _to_out(_load(session, recipe_id))


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


def replace(session: Session, recipe_id: int, doc: RecipeIn) -> RecipeOut:
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
