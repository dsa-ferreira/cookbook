import pytest
from sqlalchemy.orm import Session

from cookbook.recipes import service as recipes
from cookbook.recipes.schemas import RecipeIn
from tests.conftest import Call
from tests.recipes.factories import line, recipe_doc

pytestmark = pytest.mark.anyio


def add(session: Session, **overrides) -> int:
    return recipes.create(session, RecipeIn.model_validate(recipe_doc(**overrides))).id


UNTIMED = {"prep_time_min": None, "cook_time_min": None}


async def listed(call: Call, **arguments) -> dict:
    is_error, result = await call("list_recipes", **arguments)
    assert is_error is False, result
    return result


async def names(call: Call, **arguments) -> list[str]:
    return [r["name"] for r in (await listed(call, **arguments))["items"]]


# --- invalid arguments -------------------------------------------------------------


@pytest.mark.parametrize(
    ("arguments", "field"),
    [
        ({"sort": "tastiness"}, "sort"),
        ({"sort": "--name"}, "sort"),
        ({"ingredient_match": "some"}, "ingredient_match"),
        ({"limit": 0}, "limit"),
        ({"limit": 201}, "limit"),
        ({"offset": -1}, "offset"),
        ({"min_protein_per_serving": "lots"}, "min_protein_per_serving"),
        ({"max_total_time": "soon"}, "max_total_time"),
        ({"ingredients": ["  "]}, "ingredients"),
    ],
)
async def test_invalid_arguments_are_validation_errors(
    call: Call, arguments: dict, field: str
) -> None:
    is_error, body = await call("list_recipes", **arguments)
    assert is_error is True
    assert body["error"] == "validation_error"
    assert body["details"][0]["loc"][0] == field


# --- summaries, pagination, filters, sorting ---------------------------------------


async def test_default_page(call: Call, db_session: Session) -> None:
    for i in range(60):
        add(db_session, name=f"Recipe {i:02d}")
    body = await listed(call)
    assert len(body["items"]) == 50
    assert body["total"] == 60
    assert (body["limit"], body["offset"]) == (50, 0)
    assert [r["name"] for r in body["items"]] == [f"Recipe {i:02d}" for i in range(50)]

    rest = await listed(call, offset=50)
    assert [r["name"] for r in rest["items"]] == [f"Recipe {i:02d}" for i in range(50, 60)]
    assert rest["total"] == 60


async def test_summary_shape(call: Call, db_session: Session) -> None:
    rid = add(db_session, servings=4, protein_g=48, prep_time_min=None, cook_time_min=20)
    (summary,) = (await listed(call))["items"]
    assert summary == {
        "kcal_per_serving": 300,
        "protein_per_serving": 12,
        "carbs_per_serving": 30,
        "fat_per_serving": 14,
        "id": rid,
        "name": "Smoky hummus",
        "servings": 4,
        "prep_time_min": None,
        "cook_time_min": 20,
        "total_time_min": 20,
    }


async def test_combined_filters(call: Call, db_session: Session) -> None:
    add(db_session, name="Match", servings=2, protein_g=60, prep_time_min=10, cook_time_min=20)
    add(db_session, name="Edge", servings=1, protein_g=30, prep_time_min=None, cook_time_min=30)
    add(db_session, name="Untimed", servings=1, protein_g=40, **UNTIMED)
    add(db_session, name="Too slow", servings=1, protein_g=50, prep_time_min=10, cook_time_min=25)
    add(db_session, name="Too light", servings=2, protein_g=58, prep_time_min=5, cook_time_min=5)
    body = await listed(call, min_protein_per_serving=30, max_total_time=30)
    assert [r["name"] for r in body["items"]] == ["Edge", "Match", "Untimed"]
    assert body["total"] == 3


async def test_macro_upper_and_lower_bounds(call: Call, db_session: Session) -> None:
    add(db_session, name="Light", servings=1, kcal=300, fat_g=5)
    add(db_session, name="Medium", servings=1, kcal=500, fat_g=20)
    add(db_session, name="Heavy", servings=1, kcal=900, fat_g=50)
    bounds = {"min_kcal_per_serving": 300, "max_kcal_per_serving": 500}
    assert await names(call, **bounds) == ["Light", "Medium"]
    assert await names(call, max_fat_per_serving=20, min_fat_per_serving=5.5) == ["Medium"]


async def test_name_search_is_case_insensitive(call: Call, db_session: Session) -> None:
    add(db_session, name="Smoky hummus")
    add(db_session, name="Lentil soup")
    assert await names(call, q="HUMMUS") == ["Smoky hummus"]


async def test_sort_by_protein_descending(call: Call, db_session: Session) -> None:
    add(db_session, name="Low", servings=1, protein_g=10)
    add(db_session, name="High", servings=1, protein_g=50)
    add(db_session, name="Mid", servings=2, protein_g=60)
    assert await names(call, sort="-protein_per_serving") == ["High", "Mid", "Low"]
    assert await names(call, sort="protein_per_serving") == ["Low", "Mid", "High"]


async def test_sort_by_total_time_counts_missing_as_zero(call: Call, db_session: Session):
    add(db_session, name="Slow", prep_time_min=30, cook_time_min=60)
    add(db_session, name="Untimed", prep_time_min=None, cook_time_min=None)
    add(db_session, name="Quick", prep_time_min=5, cook_time_min=None)
    assert await names(call, sort="total_time") == ["Untimed", "Quick", "Slow"]
    assert await names(call, sort="-name") == ["Untimed", "Slow", "Quick"]


# --- ingredient filter -------------------------------------------------------------


@pytest.fixture
def r1_r2(db_session: Session) -> None:
    add(db_session, name="R1", ingredients=[line("chickpeas", 400, "g"), line("spinach", 1, "cup")])
    add(db_session, name="R2", ingredients=[line("chickpeas", 400, "g"), line("salt")])
    add(db_session, name="R3", ingredients=[line("rice", 200, "g")])


@pytest.mark.usefixtures("r1_r2")
async def test_all_ingredients_required_by_default(call: Call) -> None:
    both = ["chickpeas", "spinach"]
    assert await names(call, ingredients=both) == ["R1"]
    assert await names(call, ingredients=both, ingredient_match="all") == ["R1"]


@pytest.mark.usefixtures("r1_r2")
async def test_any_ingredient(call: Call) -> None:
    body = await listed(call, ingredients=["chickpeas", "spinach"], ingredient_match="any")
    assert [r["name"] for r in body["items"]] == ["R1", "R2"]
    assert body["total"] == 2


@pytest.mark.usefixtures("r1_r2")
async def test_ingredient_names_are_normalized(call: Call) -> None:
    assert await names(call, ingredients=[" Chickpeas"]) == ["R1", "R2"]
    # Duplicates after normalization count once for "all".
    assert await names(call, ingredients=["Spinach", "spinach "]) == ["R1"]


async def test_ingredient_repeated_on_lines_counts_once(call: Call, db_session: Session):
    add(db_session, name="Double", ingredients=[line("flour", 200, "g"), line("flour", 1, "tbsp")])
    assert await names(call, ingredients=["flour", "sugar"]) == []
    assert await names(call, ingredients=["flour"]) == ["Double"]


@pytest.mark.usefixtures("r1_r2")
async def test_unknown_ingredient_matches_nothing(call: Call) -> None:
    body = await listed(call, ingredients=["unobtainium"])
    assert body["items"] == []
    assert body["total"] == 0
