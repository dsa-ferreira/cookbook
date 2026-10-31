"""``update_recipe``: one test per scenario in specs/recipes, plus the patch edges."""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import Call
from tests.recipes.factories import line, recipe_doc

pytestmark = pytest.mark.anyio


async def create(call: Call, **overrides) -> dict:
    is_error, recipe = await call("create_recipe", recipe=recipe_doc(**overrides))
    assert is_error is False, recipe
    return recipe


async def get(call: Call, recipe_id: int) -> dict:
    _, recipe = await call("get_recipe", recipe_id=recipe_id)
    return recipe


async def update(call: Call, recipe_id: int, **changes) -> tuple[bool, dict]:
    return await call("update_recipe", recipe_id=recipe_id, changes=changes)


def without(recipe: dict, *fields: str) -> dict:
    return {k: v for k, v in recipe.items() if k not in fields}


async def test_patch_one_field(call: Call) -> None:
    before = await create(call, steps=["Soak.", "Simmer.", "Temper."])
    is_error, after = await update(call, before["id"], name="Weeknight dal")
    assert is_error is False
    assert after["name"] == "Weeknight dal"
    assert without(after, "name", "updated_at") == without(before, "name", "updated_at")
    assert await get(call, before["id"]) == after


async def test_patch_replaces_the_ingredient_list(call: Call) -> None:
    before = await create(call, ingredients=[line("apple", 2, "piece"), line("banana", 1, "piece")])
    is_error, _ = await update(call, before["id"], ingredients=[line("cherry", 100, "g")])
    assert is_error is False
    after = await get(call, before["id"])
    assert [(i["name"], i["quantity"], i["unit"]) for i in after["ingredients"]] == [
        ("cherry", 100, "g")
    ]
    assert after["steps"] == before["steps"]


async def test_null_clears_an_optional_field(call: Call) -> None:
    before = await create(call, prep_time_min=10, cook_time_min=20)
    is_error, after = await update(call, before["id"], prep_time_min=None)
    assert is_error is False
    assert after["prep_time_min"] is None
    assert after["total_time_min"] == 20


async def test_null_clears_description(call: Call) -> None:
    before = await create(call)
    _, after = await update(call, before["id"], description=None)
    assert after["description"] is None


@pytest.mark.parametrize("field", ["servings", "name", "steps", "ingredients", "protein_g"])
async def test_null_on_a_required_field_is_rejected(call: Call, field: str) -> None:
    before = await create(call)
    is_error, body = await update(call, before["id"], **{field: None})
    assert is_error is True
    assert body["error"] == "validation_error"
    assert ["changes", field] in [d["loc"] for d in body["details"]]
    assert await get(call, before["id"]) == before


async def test_empty_patch_is_rejected(call: Call) -> None:
    before = await create(call)
    is_error, body = await update(call, before["id"])
    assert is_error is True
    assert body["error"] == "validation_error"
    assert "at least one field" in body["details"][0]["msg"]


async def test_derived_fields_are_not_accepted(call: Call) -> None:
    before = await create(call)
    is_error, body = await update(call, before["id"], protein_per_serving=10)
    assert (is_error, body["error"]) == (True, "validation_error")
    assert await get(call, before["id"]) == before


async def test_update_unknown_recipe(call: Call) -> None:
    is_error, body = await update(call, 999999, name="x")
    assert is_error is True
    assert body["error"] == "not_found"


async def test_failed_update_leaves_recipe_unchanged(call: Call) -> None:
    before = await create(call)
    is_error, body = await update(
        call, before["id"], name="Changed", ingredients=[line("new thing", 1, "handful")]
    )
    assert is_error is True
    assert body["error"] == "validation_error"
    assert "handful" in body["message"]
    assert await get(call, before["id"]) == before
    _, found = await call("search_ingredients", q="new thing")
    assert found["items"] == []


async def test_cross_field_line_rule_is_checked(call: Call) -> None:
    before = await create(call)
    is_error, body = await update(call, before["id"], ingredients=[line("eggs", 2)])
    assert (is_error, body["error"]) == (True, "validation_error")
    assert body["details"][0]["loc"] == ["changes", "ingredients", 0]
    assert await get(call, before["id"]) == before


async def test_update_returns_the_stored_recipe(call: Call, db_session: Session) -> None:
    before = await create(call)
    # Tests share one transaction, where now() doesn't move; backdate instead.
    db_session.execute(
        text("UPDATE recipes SET updated_at = updated_at - interval '1 hour' WHERE id = :id"),
        {"id": before["id"]},
    )
    db_session.commit()
    backdated = await get(call, before["id"])

    is_error, after = await update(call, before["id"], steps=["Only step."])
    assert is_error is False
    assert after["steps"] == ["Only step."]
    assert after["ingredients"] == before["ingredients"]
    assert after["updated_at"] > backdated["updated_at"]
    assert after == await get(call, before["id"])


async def test_changing_servings_updates_per_serving_values(call: Call) -> None:
    before = await create(call, servings=3, protein_g=120)
    assert before["protein_per_serving"] == 40
    _, after = await update(call, before["id"], servings=4)
    assert after["protein_per_serving"] == 30
    assert after["protein_g"] == 120


async def test_update_adds_a_new_ingredient(call: Call) -> None:
    before = await create(call)
    is_error, _ = await update(call, before["id"], ingredients=[line("sumac", 1, "tsp")])
    assert is_error is False
    _, found = await call("search_ingredients", q="sumac")
    assert [i["name"] for i in found["items"]] == ["sumac"]


async def test_sending_every_field_replaces_the_recipe(call: Call) -> None:
    before = await create(call)
    full = recipe_doc(name="Brand new", description=None, steps=["a", "b"], servings=2)
    is_error, after = await update(call, before["id"], **full)
    assert is_error is False
    assert (after["name"], after["description"], after["steps"], after["servings"]) == (
        "Brand new",
        None,
        ["a", "b"],
        2,
    )
    assert after["created_at"] == before["created_at"]
