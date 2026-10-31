from decimal import Decimal

import pytest
from pydantic import ValidationError

from cookbook.recipes.schemas import RecipeListParams


def test_defaults() -> None:
    p = RecipeListParams()
    assert (p.sort, p.limit, p.offset, p.ingredient_match, p.ingredient) == (
        "name",
        50,
        0,
        "all",
        [],
    )


def test_ingredients_are_normalized_and_deduplicated() -> None:
    p = RecipeListParams(ingredient=[" Chickpeas", "chickpeas", "Spinach"])
    assert p.ingredient == ["chickpeas", "spinach"]


@pytest.mark.parametrize("sort", ["name", "-name", "total_time", "-protein_per_serving"])
def test_valid_sort(sort: str) -> None:
    assert RecipeListParams(sort=sort).sort == sort


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sort", "tastiness"),
        ("sort", "--name"),
        ("ingredient_match", "some"),
        ("limit", 0),
        ("limit", 201),
        ("offset", -1),
        ("min_protein_per_serving", "lots"),
        ("max_total_time", "soon"),
        ("ingredient", ["  "]),
    ],
)
def test_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as exc:
        RecipeListParams.model_validate({field: value})
    assert exc.value.errors()[0]["loc"][0] == field


def test_bounds_parse_from_strings() -> None:
    p = RecipeListParams.model_validate({"min_protein_per_serving": "30", "limit": "200"})
    assert p.min_protein_per_serving == Decimal(30)
    assert p.limit == 200
