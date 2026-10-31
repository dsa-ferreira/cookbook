"""Constraints and generated columns, exercised directly against Postgres."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient
from cookbook.recipes.models import Recipe, RecipeIngredient


def make_recipe(**overrides: object) -> Recipe:
    values: dict[str, object] = {
        "name": "Test",
        "servings": 3,
        "kcal": Decimal("600"),
        "protein_g": Decimal("100"),
        "carbs_g": Decimal("50"),
        "fat_g": Decimal("20"),
    }
    values.update(overrides)
    return Recipe(**values)


def test_per_serving_values_are_generated(db_session: Session) -> None:
    recipe = make_recipe()
    db_session.add(recipe)
    db_session.flush()
    db_session.refresh(recipe)
    assert recipe.protein_g_per_serving == Decimal("33.3")
    assert recipe.kcal_per_serving == Decimal("200.0")
    assert recipe.carbs_g_per_serving == Decimal("16.7")
    assert recipe.fat_g_per_serving == Decimal("6.7")


@pytest.mark.parametrize(
    ("prep", "cook", "total"),
    [(None, 25, 25), (10, None, 10), (10, 25, 35), (None, None, None)],
)
def test_total_time(db_session: Session, prep: int | None, cook: int | None, total: int | None):
    recipe = make_recipe(prep_time_min=prep, cook_time_min=cook)
    db_session.add(recipe)
    db_session.flush()
    db_session.refresh(recipe)
    assert recipe.total_time_min == total


@pytest.mark.parametrize(("quantity", "unit"), [(Decimal("2"), None), (None, "g")])
def test_quantity_and_unit_both_or_neither(
    db_session: Session, quantity: Decimal | None, unit: str | None
) -> None:
    recipe = make_recipe()
    ingredient = Ingredient(name="salt")
    db_session.add_all([recipe, ingredient])
    db_session.flush()
    db_session.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ingredient.id,
            position=0,
            quantity=quantity,
            unit=unit,
        )
    )
    with pytest.raises(IntegrityError, match="quantity_unit_together"):
        db_session.flush()


def test_line_without_quantity_or_unit_is_allowed(db_session: Session) -> None:
    recipe = make_recipe()
    ingredient = Ingredient(name="salt")
    db_session.add_all([recipe, ingredient])
    db_session.flush()
    db_session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=ingredient.id, position=0))
    db_session.flush()


@pytest.mark.parametrize("servings", [0, -1])
def test_servings_must_be_positive(db_session: Session, servings: int) -> None:
    db_session.add(make_recipe(servings=servings))
    with pytest.raises(IntegrityError, match="servings_positive"):
        db_session.flush()
