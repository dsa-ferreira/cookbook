import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient
from cookbook.recipes.models import Recipe
from cookbook.units.models import Unit
from tests.conftest import Call
from tests.recipes.factories import line, recipe_doc

pytestmark = pytest.mark.anyio


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def ingredient_names(session: Session) -> set[str]:
    return set(session.scalars(select(Ingredient.name)))


def locs(body: dict) -> list[list]:
    return [d["loc"] for d in body["details"]]


async def test_create_returns_stored_recipe(call: Call) -> None:
    doc = recipe_doc(servings=4, steps=["Cook."], ingredients=[line("rice", 200, "g")])
    is_error, body = await call("create_recipe", recipe=doc)
    assert is_error is False
    assert isinstance(body["id"], int)
    assert body["name"] == doc["name"]
    assert body["servings"] == 4
    assert body["steps"] == ["Cook."]
    assert body["ingredients"][0] | {"ingredient_id": None} == {
        "ingredient_id": None,
        "name": "rice",
        "quantity": 200,
        "unit": "g",
        "prep_note": None,
        "optional": False,
    }
    assert (body["kcal"], body["protein_g"], body["carbs_g"], body["fat_g"]) == (1200, 48, 120, 56)
    assert body["protein_per_serving"] == 12
    assert body["total_time_min"] == 15
    assert body["created_at"] and body["updated_at"]


async def test_decimal_macro_round_trips_as_number(call: Call) -> None:
    _, created = await call("create_recipe", recipe=recipe_doc(protein_g=12.3))
    _, body = await call("get_recipe", recipe_id=created["id"])
    assert body["protein_g"] == 12.3


async def test_missing_macro_names_the_field(call: Call, db_session: Session) -> None:
    doc = recipe_doc()
    del doc["protein_g"]
    is_error, body = await call("create_recipe", recipe=doc)
    assert is_error is True
    assert body["error"] == "validation_error"
    assert ["recipe", "protein_g"] in locs(body)
    assert count(db_session, Recipe) == 0


@pytest.mark.parametrize(
    ("overrides", "loc"),
    [
        ({"servings": 0}, ["recipe", "servings"]),
        ({"steps": []}, ["recipe", "steps"]),
        ({"protein_per_serving": 12}, ["recipe", "protein_per_serving"]),
        ({"ingredients": [line("eggs", 2)]}, ["recipe", "ingredients", 0]),
        ({"ingredients": [line("   ")]}, ["recipe", "ingredients", 0, "name"]),
    ],
    ids=["zero-servings", "no-steps", "per-serving-input", "quantity-without-unit", "blank-name"],
)
async def test_invalid_document_is_a_validation_error(
    call: Call, db_session: Session, overrides: dict, loc: list
) -> None:
    is_error, body = await call("create_recipe", recipe=recipe_doc(**overrides))
    assert is_error is True
    assert body["error"] == "validation_error"
    assert loc in locs(body)
    assert count(db_session, Recipe) == 0


async def test_unknown_unit_is_rejected_and_named(call: Call, db_session: Session) -> None:
    doc = recipe_doc(ingredients=[line("rice", 200, "g"), line("spinach", 1, "handful")])
    is_error, body = await call("create_recipe", recipe=doc)
    assert is_error is True
    assert body["error"] == "validation_error"
    assert "handful" in body["message"]
    assert locs(body) == [["ingredients", 1, "unit"]]
    assert db_session.get(Unit, "handful") is None
    assert count(db_session, Recipe) == 0


async def test_rejected_recipe_creates_no_ingredients(call: Call, db_session: Session) -> None:
    doc = recipe_doc(ingredients=[line("sumac", 1, "tsp"), line("lemon", 1, "handful")])
    is_error, _ = await call("create_recipe", recipe=doc)
    assert is_error is True
    assert "sumac" not in ingredient_names(db_session)


async def test_new_ingredient_is_added_to_catalogue(call: Call, db_session: Session) -> None:
    is_error, _ = await call(
        "create_recipe", recipe=recipe_doc(ingredients=[line("Za'atar", 1, "tbsp")])
    )
    assert is_error is False
    assert "za'atar" in ingredient_names(db_session)


async def test_ingredient_reused_across_case_variants(call: Call, db_session: Session) -> None:
    _, first = await call(
        "create_recipe", recipe=recipe_doc(ingredients=[line("garlic", 2, "clove")])
    )
    before = count(db_session, Ingredient)
    other = recipe_doc(name="Other", ingredients=[line("  Garlic ", 3, "clove")])
    is_error, second = await call("create_recipe", recipe=other)
    assert is_error is False
    assert count(db_session, Ingredient) == before
    assert second["ingredients"][0]["name"] == "garlic"
    assert second["ingredients"][0]["ingredient_id"] == first["ingredients"][0]["ingredient_id"]
