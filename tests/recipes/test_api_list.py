import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from cookbook.recipes import service as recipes
from cookbook.recipes.schemas import RecipeIn
from tests.recipes.factories import line, recipe_doc


def add(session: Session, **overrides) -> int:
    return recipes.create(session, RecipeIn.model_validate(recipe_doc(**overrides))).id


UNTIMED = {"prep_time_min": None, "cook_time_min": None}


def names(resp) -> list[str]:
    assert resp.status_code == 200, resp.get_json()
    return [r["name"] for r in resp.get_json()["items"]]


# --- 7.1 invalid parameters ----------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "sort=tastiness",
        "ingredient_match=some",
        "limit=0",
        "limit=201",
        "offset=-1",
        "min_protein_per_serving=lots",
        "max_total_time=soon",
        "ingredient=%20%20",
        "unknown=1",
    ],
)
def test_invalid_list_params_are_422(client: FlaskClient, query: str) -> None:
    resp = client.get(f"/recipes?{query}")
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "validation_error"


# --- 7.2 summaries, pagination, filters, sorting ----------------------------------


def test_default_page(client: FlaskClient, db_session: Session) -> None:
    for i in range(60):
        add(db_session, name=f"Recipe {i:02d}")
    resp = client.get("/recipes")
    body = resp.get_json()
    assert len(body["items"]) == 50
    assert body["total"] == 60
    assert (body["limit"], body["offset"]) == (50, 0)
    assert names(resp) == [f"Recipe {i:02d}" for i in range(50)]

    rest = client.get("/recipes?offset=50").get_json()
    assert [r["name"] for r in rest["items"]] == [f"Recipe {i:02d}" for i in range(50, 60)]
    assert rest["total"] == 60


def test_summary_shape(client: FlaskClient, db_session: Session) -> None:
    rid = add(db_session, servings=4, protein_g=48, prep_time_min=None, cook_time_min=20)
    (summary,) = client.get("/recipes").get_json()["items"]
    assert summary == {
        "kcal_per_serving": 300.0,
        "protein_per_serving": 12.0,
        "carbs_per_serving": 30.0,
        "fat_per_serving": 14.0,
        "id": rid,
        "name": "Smoky hummus",
        "servings": 4,
        "prep_time_min": None,
        "cook_time_min": 20,
        "total_time_min": 20,
    }


def test_combined_filters(client: FlaskClient, db_session: Session) -> None:
    # protein per serving / total time
    add(db_session, name="Match", servings=2, protein_g=60, prep_time_min=10, cook_time_min=20)
    add(db_session, name="Edge", servings=1, protein_g=30, prep_time_min=None, cook_time_min=30)
    add(db_session, name="Untimed", servings=1, protein_g=40, **UNTIMED)
    add(db_session, name="Too slow", servings=1, protein_g=50, prep_time_min=10, cook_time_min=25)
    add(db_session, name="Too light", servings=2, protein_g=58, prep_time_min=5, cook_time_min=5)
    resp = client.get("/recipes?min_protein_per_serving=30&max_total_time=30")
    assert names(resp) == ["Edge", "Match", "Untimed"]
    assert resp.get_json()["total"] == 3


def test_macro_upper_and_lower_bounds(client: FlaskClient, db_session: Session) -> None:
    add(db_session, name="Light", servings=1, kcal=300, fat_g=5)
    add(db_session, name="Medium", servings=1, kcal=500, fat_g=20)
    add(db_session, name="Heavy", servings=1, kcal=900, fat_g=50)
    assert names(client.get("/recipes?min_kcal_per_serving=300&max_kcal_per_serving=500")) == [
        "Light",
        "Medium",
    ]
    assert names(client.get("/recipes?max_fat_per_serving=20&min_fat_per_serving=6")) == ["Medium"]


def test_name_search_is_case_insensitive(client: FlaskClient, db_session: Session) -> None:
    add(db_session, name="Smoky hummus")
    add(db_session, name="Lentil soup")
    assert names(client.get("/recipes?q=HUMMUS")) == ["Smoky hummus"]


def test_sort_by_protein_descending(client: FlaskClient, db_session: Session) -> None:
    add(db_session, name="Low", servings=1, protein_g=10)
    add(db_session, name="High", servings=1, protein_g=50)
    add(db_session, name="Mid", servings=2, protein_g=60)
    assert names(client.get("/recipes?sort=-protein_per_serving")) == ["High", "Mid", "Low"]
    assert names(client.get("/recipes?sort=protein_per_serving")) == ["Low", "Mid", "High"]


def test_sort_by_total_time_counts_missing_as_zero(client: FlaskClient, db_session: Session):
    add(db_session, name="Slow", prep_time_min=30, cook_time_min=60)
    add(db_session, name="Untimed", prep_time_min=None, cook_time_min=None)
    add(db_session, name="Quick", prep_time_min=5, cook_time_min=None)
    assert names(client.get("/recipes?sort=total_time")) == ["Untimed", "Quick", "Slow"]
    assert names(client.get("/recipes?sort=-name")) == ["Untimed", "Slow", "Quick"]


# --- 7.3 ingredient filter ------------------------------------------------------


@pytest.fixture
def r1_r2(db_session: Session) -> None:
    add(db_session, name="R1", ingredients=[line("chickpeas", 400, "g"), line("spinach", 1, "cup")])
    add(db_session, name="R2", ingredients=[line("chickpeas", 400, "g"), line("salt")])
    add(db_session, name="R3", ingredients=[line("rice", 200, "g")])


@pytest.mark.usefixtures("r1_r2")
def test_all_ingredients_required_by_default(client: FlaskClient) -> None:
    assert names(client.get("/recipes?ingredient=chickpeas&ingredient=spinach")) == ["R1"]
    explicit = "/recipes?ingredient=chickpeas&ingredient=spinach&ingredient_match=all"
    assert names(client.get(explicit)) == ["R1"]


@pytest.mark.usefixtures("r1_r2")
def test_any_ingredient(client: FlaskClient) -> None:
    resp = client.get("/recipes?ingredient=chickpeas&ingredient=spinach&ingredient_match=any")
    assert names(resp) == ["R1", "R2"]
    assert resp.get_json()["total"] == 2


@pytest.mark.usefixtures("r1_r2")
def test_ingredient_names_are_normalized(client: FlaskClient) -> None:
    assert names(client.get("/recipes?ingredient=%20Chickpeas")) == ["R1", "R2"]
    # Duplicates after normalization count once for "all".
    assert names(client.get("/recipes?ingredient=Spinach&ingredient=spinach%20")) == ["R1"]


def test_ingredient_repeated_on_lines_counts_once(client: FlaskClient, db_session: Session):
    add(db_session, name="Double", ingredients=[line("flour", 200, "g"), line("flour", 1, "tbsp")])
    assert names(client.get("/recipes?ingredient=flour&ingredient=sugar")) == []
    assert names(client.get("/recipes?ingredient=flour")) == ["Double"]


@pytest.mark.usefixtures("r1_r2")
def test_unknown_ingredient_matches_nothing(client: FlaskClient) -> None:
    resp = client.get("/recipes?ingredient=unobtainium")
    assert names(resp) == []
    assert resp.get_json()["total"] == 0
