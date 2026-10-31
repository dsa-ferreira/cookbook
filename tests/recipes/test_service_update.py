from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from cookbook.common.errors import InvalidInputError, NotFoundError
from cookbook.ingredients.models import Ingredient
from cookbook.recipes import service
from cookbook.recipes.schemas import RecipeIn, RecipeOut, RecipePatch
from tests.recipes.factories import line, recipe_doc


def create(session: Session, **overrides) -> RecipeOut:
    return service.create(session, RecipeIn.model_validate(recipe_doc(**overrides)))


def update(session: Session, recipe_id: int, **changes) -> RecipeOut:
    return service.update(session, recipe_id, RecipePatch.model_validate(changes))


def unchanged_fields(recipe: RecipeOut) -> dict:
    return recipe.model_dump(exclude={"name", "updated_at"})


def test_patching_one_field_keeps_the_rest(db_session: Session) -> None:
    before = create(db_session, steps=["one", "two", "three"])
    after = update(db_session, before.id, name="Weeknight dal")
    assert after.name == "Weeknight dal"
    assert unchanged_fields(after) == unchanged_fields(before)
    assert service.get(db_session, before.id) == after


def test_ingredients_patch_replaces_the_whole_list(db_session: Session) -> None:
    before = create(db_session, ingredients=[line("apple", 2, "piece"), line("banana", 1, "piece")])
    after = update(db_session, before.id, ingredients=[line("cherry", 100, "g")])
    assert [(i.name, i.quantity, i.unit) for i in after.ingredients] == [
        ("cherry", Decimal(100), "g")
    ]
    assert after.steps == before.steps


def test_longer_lists_reuse_positions(db_session: Session) -> None:
    before = create(db_session, ingredients=[line("a", 1, "g")], steps=["one"])
    lines = [line("b", 1, "g"), line("c", 2, "g"), line("d", 3, "g")]
    after = update(db_session, before.id, ingredients=lines, steps=["x", "y"])
    assert [i.name for i in after.ingredients] == ["b", "c", "d"]
    assert after.steps == ["x", "y"]


def test_null_clears_prep_time(db_session: Session) -> None:
    before = create(db_session, prep_time_min=10, cook_time_min=20)
    after = update(db_session, before.id, prep_time_min=None)
    assert after.prep_time_min is None
    assert after.total_time_min == 20


def test_servings_change_updates_per_serving(db_session: Session) -> None:
    before = create(db_session, servings=3, protein_g=120)
    assert before.protein_per_serving == Decimal("40.0")
    after = update(db_session, before.id, servings=4)
    assert after.protein_per_serving == Decimal("30.0")
    assert after.protein_g == Decimal(120)


def test_unknown_unit_leaves_recipe_unchanged(db_session: Session) -> None:
    before = create(db_session)
    with pytest.raises(InvalidInputError) as exc:
        update(db_session, before.id, name="Changed", ingredients=[line("sumac", 1, "handful")])
    assert "handful" in exc.value.message
    assert exc.value.details[0]["loc"] == ["ingredients", 0, "unit"]
    assert service.get(db_session, before.id) == before
    assert db_session.scalar(select(Ingredient).where(Ingredient.name == "sumac")) is None


def test_merged_document_is_validated_as_a_whole(db_session: Session) -> None:
    before = create(db_session)
    # A quantity without a unit is a cross-field rule on the line.
    with pytest.raises(ValidationError) as exc:
        update(db_session, before.id, ingredients=[{"name": "eggs", "quantity": 2}])
    assert exc.value.errors()[0]["loc"][:2] == ("ingredients", 0)
    assert service.get(db_session, before.id) == before


def test_update_adds_new_ingredient_to_catalogue(db_session: Session) -> None:
    before = create(db_session)
    update(db_session, before.id, ingredients=[line("sumac", 1, "tsp")])
    assert db_session.scalar(select(Ingredient).where(Ingredient.name == "sumac")) is not None


def test_unknown_id_raises_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        update(db_session, 999999, name="x")


def test_updated_at_advances(db_session: Session) -> None:
    before = create(db_session)
    # Tests share one transaction, where now() doesn't move; backdate instead.
    db_session.execute(
        text(
            "UPDATE recipes SET created_at = created_at - interval '1 hour',"
            " updated_at = updated_at - interval '1 hour' WHERE id = :id"
        ),
        {"id": before.id},
    )
    db_session.commit()
    backdated = service.get(db_session, before.id)

    after = update(db_session, before.id, steps=["New step."])
    assert after.updated_at > backdated.updated_at
    assert after.created_at == backdated.created_at
