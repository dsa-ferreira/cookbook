from decimal import Decimal

import pytest
from pydantic import ValidationError

from cookbook.recipes.schemas import SORT_KEYS, RecipeListParams


def test_defaults() -> None:
    p = RecipeListParams()
    assert (p.sort, p.limit, p.offset, p.all_ingredients, p.any_ingredients) == (
        "name",
        50,
        0,
        [],
        [],
    )


@pytest.mark.parametrize("field", ["all_ingredients", "any_ingredients"])
def test_ingredients_are_normalized_and_deduplicated(field: str) -> None:
    p = RecipeListParams.model_validate({field: [" Chickpeas", "chickpeas", "Spinach"]})
    assert getattr(p, field) == ["chickpeas", "spinach"]


def test_sort_keys_are_the_unprefixed_values() -> None:
    assert SORT_KEYS == (
        "name",
        "created_at",
        "total_time",
        "kcal_per_serving",
        "protein_per_serving",
        "carbs_per_serving",
        "fat_per_serving",
    )


@pytest.mark.parametrize("sort", ["name", "-name", "total_time", "-protein_per_serving"])
def test_valid_sort(sort: str) -> None:
    assert RecipeListParams(sort=sort).sort == sort


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sort", "tastiness"),
        ("sort", "--name"),
        ("ingredients", ["chickpeas"]),
        ("ingredient_match", "any"),
        ("limit", 0),
        ("limit", 201),
        ("offset", -1),
        ("min_protein_per_serving", "lots"),
        ("max_total_time", "soon"),
        ("all_ingredients", ["  "]),
        ("any_ingredients", ["chickpeas", ""]),
        ("all_ingredients", {"chicken": "all"}),
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
