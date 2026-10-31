from flask.testing import FlaskClient

from tests.recipes.factories import line, recipe_doc


def create(client: FlaskClient, **overrides) -> dict:
    resp = client.post("/recipes", json=recipe_doc(**overrides))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_replace_swaps_the_ingredient_list(client: FlaskClient) -> None:
    created = create(client, ingredients=[line("apple", 2, "piece"), line("banana", 1, "piece")])
    resp = client.put(
        f"/recipes/{created['id']}",
        json=recipe_doc(ingredients=[line("cherry", 100, "g")], steps=["Only step."]),
    )
    assert resp.status_code == 200
    body = client.get(f"/recipes/{created['id']}").get_json()
    assert [i["name"] for i in body["ingredients"]] == ["cherry"]
    assert body["steps"] == ["Only step."]
    assert body["id"] == created["id"]
    assert body["created_at"] == created["created_at"]


def test_replace_with_same_positions_and_more_lines(client: FlaskClient) -> None:
    created = create(client, ingredients=[line("a", 1, "g")], steps=["one"])
    lines = [line("b", 1, "g"), line("c", 2, "g"), line("d", 3, "g")]
    resp = client.put(f"/recipes/{created['id']}", json=recipe_doc(ingredients=lines))
    assert resp.status_code == 200
    assert [i["name"] for i in resp.get_json()["ingredients"]] == ["b", "c", "d"]


def test_changing_servings_updates_per_serving_values(client: FlaskClient) -> None:
    created = create(client, servings=3, protein_g=120)
    assert created["protein_per_serving"] == 40.0
    resp = client.put(f"/recipes/{created['id']}", json=recipe_doc(servings=4, protein_g=120))
    assert resp.status_code == 200
    assert resp.get_json()["protein_per_serving"] == 30.0
    assert client.get(f"/recipes/{created['id']}").get_json()["protein_per_serving"] == 30.0


def test_failed_replace_leaves_recipe_unchanged(client: FlaskClient) -> None:
    created = create(client)
    before = client.get(f"/recipes/{created['id']}").get_json()

    bad_unit = recipe_doc(name="Changed", ingredients=[line("new thing", 1, "handful")])
    resp = client.put(f"/recipes/{created['id']}", json=bad_unit)
    assert resp.status_code == 422
    assert "handful" in resp.get_json()["message"]

    bad_schema = recipe_doc(name="Changed", steps=[])
    assert client.put(f"/recipes/{created['id']}", json=bad_schema).status_code == 422

    assert client.get(f"/recipes/{created['id']}").get_json() == before
    names = [i["name"] for i in client.get("/ingredients?q=new thing").get_json()["items"]]
    assert names == []


def test_replace_unknown_recipe(client: FlaskClient) -> None:
    resp = client.put("/recipes/999999", json=recipe_doc())
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"
