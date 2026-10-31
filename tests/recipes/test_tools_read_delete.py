import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cookbook.recipes.models import RecipeIngredient, RecipeStep
from tests.conftest import Call
from tests.recipes.factories import line, recipe_doc

pytestmark = pytest.mark.anyio


async def create(call: Call, **overrides) -> dict:
    is_error, recipe = await call("create_recipe", recipe=recipe_doc(**overrides))
    assert is_error is False, recipe
    return recipe


async def get(call: Call, recipe_id: int) -> dict:
    is_error, recipe = await call("get_recipe", recipe_id=recipe_id)
    assert is_error is False, recipe
    return recipe


# --- get_recipe --------------------------------------------------------------------


async def test_read_existing_recipe(call: Call) -> None:
    created = await create(
        call,
        servings=3,
        protein_g=100,
        prep_time_min=None,
        cook_time_min=25,
        ingredients=[line("chickpeas", 400, "g", prep_note="drained"), line("salt")],
    )
    body = await get(call, created["id"])
    assert body == created
    assert body["protein_per_serving"] == 33.3
    assert body["kcal_per_serving"] == 400
    assert body["total_time_min"] == 25
    assert body["steps"] == ["Blend everything.", "Season and serve."]
    chickpeas, salt = body["ingredients"]
    assert (chickpeas["name"], chickpeas["quantity"], chickpeas["unit"]) == ("chickpeas", 400, "g")
    assert chickpeas["prep_note"] == "drained"
    assert (salt["name"], salt["quantity"], salt["unit"]) == ("salt", None, None)


async def test_read_unknown_recipe(call: Call) -> None:
    is_error, body = await call("get_recipe", recipe_id=999999)
    assert is_error is True
    assert body["error"] == "not_found"


async def test_lines_and_steps_keep_their_order(call: Call) -> None:
    created = await create(
        call,
        steps=["third? no, first", "second", "last"],
        ingredients=[line("flour", 200, "g"), line("butter", 100, "g"), line("sugar", 50, "g")],
    )
    body = await get(call, created["id"])
    assert [i["name"] for i in body["ingredients"]] == ["flour", "butter", "sugar"]
    assert body["steps"] == ["third? no, first", "second", "last"]


async def test_same_ingredient_on_two_lines(call: Call) -> None:
    created = await create(call, ingredients=[line("flour", 200, "g"), line("Flour", 1, "tbsp")])
    lines = (await get(call, created["id"]))["ingredients"]
    assert [(i["name"], i["unit"]) for i in lines] == [("flour", "g"), ("flour", "tbsp")]
    assert lines[0]["ingredient_id"] == lines[1]["ingredient_id"]


# --- delete_recipe -----------------------------------------------------------------


async def test_delete_keeps_catalogue_ingredients(call: Call, db_session: Session) -> None:
    created = await create(call, ingredients=[line("tahini", 2, "tbsp")])
    is_error, body = await call("delete_recipe", recipe_id=created["id"])
    assert is_error is False
    assert body == {"id": created["id"], "deleted": True}

    is_error, body = await call("get_recipe", recipe_id=created["id"])
    assert (is_error, body["error"]) == (True, "not_found")
    _, found = await call("search_ingredients", q="tahini")
    assert [i["name"] for i in found["items"]] == ["tahini"]
    for model in (RecipeStep, RecipeIngredient):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0


async def test_delete_unknown_recipe(call: Call) -> None:
    is_error, body = await call("delete_recipe", recipe_id=999999)
    assert is_error is True
    assert body["error"] == "not_found"
