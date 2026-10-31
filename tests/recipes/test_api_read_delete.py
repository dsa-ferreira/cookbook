from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cookbook.recipes.models import RecipeIngredient, RecipeStep
from tests.recipes.factories import line, recipe_doc


def create(client: FlaskClient, **overrides) -> dict:
    resp = client.post("/recipes", json=recipe_doc(**overrides))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_read_existing_recipe(client: FlaskClient) -> None:
    created = create(
        client,
        servings=3,
        protein_g=100,
        prep_time_min=None,
        cook_time_min=25,
        ingredients=[line("chickpeas", 400, "g", prep_note="drained"), line("salt")],
    )
    resp = client.get(f"/recipes/{created['id']}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == created
    assert body["protein_per_serving"] == 33.3
    assert body["kcal_per_serving"] == 400.0
    assert body["total_time_min"] == 25
    assert body["steps"] == ["Blend everything.", "Season and serve."]
    chickpeas, salt = body["ingredients"]
    assert (chickpeas["name"], chickpeas["quantity"], chickpeas["unit"]) == ("chickpeas", 400, "g")
    assert chickpeas["prep_note"] == "drained"
    assert (salt["name"], salt["quantity"], salt["unit"]) == ("salt", None, None)


def test_read_unknown_recipe(client: FlaskClient) -> None:
    resp = client.get("/recipes/999999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"


def test_lines_and_steps_keep_their_order(client: FlaskClient) -> None:
    created = create(
        client,
        steps=["third? no, first", "second", "last"],
        ingredients=[line("flour", 200, "g"), line("butter", 100, "g"), line("sugar", 50, "g")],
    )
    body = client.get(f"/recipes/{created['id']}").get_json()
    assert [i["name"] for i in body["ingredients"]] == ["flour", "butter", "sugar"]
    assert body["steps"] == ["third? no, first", "second", "last"]


def test_same_ingredient_on_two_lines(client: FlaskClient) -> None:
    created = create(client, ingredients=[line("flour", 200, "g"), line("Flour", 1, "tbsp")])
    lines = client.get(f"/recipes/{created['id']}").get_json()["ingredients"]
    assert [(i["name"], i["unit"]) for i in lines] == [("flour", "g"), ("flour", "tbsp")]
    assert lines[0]["ingredient_id"] == lines[1]["ingredient_id"]


def test_delete_keeps_catalogue_ingredients(client: FlaskClient, db_session: Session) -> None:
    created = create(client, ingredients=[line("tahini", 2, "tbsp")])
    resp = client.delete(f"/recipes/{created['id']}")
    assert resp.status_code == 204
    assert resp.data == b""
    assert client.get(f"/recipes/{created['id']}").status_code == 404
    names = [i["name"] for i in client.get("/ingredients?q=tahini").get_json()["items"]]
    assert names == ["tahini"]
    for model in (RecipeStep, RecipeIngredient):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0


def test_delete_unknown_recipe(client: FlaskClient) -> None:
    resp = client.delete("/recipes/999999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"
