from flask.testing import FlaskClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cookbook.ingredients.models import Ingredient
from cookbook.recipes.models import Recipe
from cookbook.units.models import Unit
from tests.recipes.factories import line, recipe_doc


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def ingredient_names(session: Session) -> set[str]:
    return set(session.scalars(select(Ingredient.name)))


def test_create_returns_stored_recipe(client: FlaskClient) -> None:
    doc = recipe_doc(servings=4, steps=["Cook."], ingredients=[line("rice", 200, "g")])
    resp = client.post("/recipes", json=doc)
    assert resp.status_code == 201
    body = resp.get_json()
    assert isinstance(body["id"], int)
    assert resp.headers["Location"] == f"/recipes/{body['id']}"
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
    assert body["protein_per_serving"] == 12.0
    assert body["total_time_min"] == 15
    assert body["created_at"] and body["updated_at"]


def test_missing_macro_names_the_field(client: FlaskClient, db_session: Session) -> None:
    doc = recipe_doc()
    del doc["protein_g"]
    resp = client.post("/recipes", json=doc)
    assert resp.status_code == 422
    assert ["protein_g"] in [d["loc"] for d in resp.get_json()["details"]]
    assert count(db_session, Recipe) == 0


def test_unknown_unit_is_rejected_and_named(client: FlaskClient, db_session: Session) -> None:
    doc = recipe_doc(ingredients=[line("rice", 200, "g"), line("spinach", 1, "handful")])
    resp = client.post("/recipes", json=doc)
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["error"] == "validation_error"
    assert "handful" in body["message"]
    assert body["details"][0]["loc"] == ["ingredients", 1, "unit"]
    assert db_session.get(Unit, "handful") is None
    assert count(db_session, Recipe) == 0


def test_rejected_recipe_creates_no_ingredients(client: FlaskClient, db_session: Session) -> None:
    doc = recipe_doc(ingredients=[line("sumac", 1, "tsp"), line("lemon", 1, "handful")])
    assert client.post("/recipes", json=doc).status_code == 422
    assert "sumac" not in ingredient_names(db_session)


def test_new_ingredient_is_added_to_catalogue(client: FlaskClient, db_session: Session) -> None:
    resp = client.post("/recipes", json=recipe_doc(ingredients=[line("Za'atar", 1, "tbsp")]))
    assert resp.status_code == 201
    assert "za'atar" in ingredient_names(db_session)


def test_ingredient_reused_across_case_variants(client: FlaskClient, db_session: Session) -> None:
    first = client.post("/recipes", json=recipe_doc(ingredients=[line("garlic", 2, "clove")]))
    before = count(db_session, Ingredient)
    second = client.post(
        "/recipes", json=recipe_doc(name="Other", ingredients=[line("  Garlic ", 3, "clove")])
    )
    assert second.status_code == 201
    assert count(db_session, Ingredient) == before
    first_line = first.get_json()["ingredients"][0]
    second_line = second.get_json()["ingredients"][0]
    assert second_line["name"] == "garlic"
    assert second_line["ingredient_id"] == first_line["ingredient_id"]


def test_blank_ingredient_name_is_422(client: FlaskClient) -> None:
    resp = client.post("/recipes", json=recipe_doc(ingredients=[line("   ")]))
    assert resp.status_code == 422
