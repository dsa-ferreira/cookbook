from decimal import Decimal

import pytest
from pydantic import ValidationError

from cookbook.recipes.schemas import RecipeIn, RecipeListParams, RecipePatch
from tests.recipes.factories import line, recipe_doc


def error_locs(doc: dict) -> list[tuple]:
    with pytest.raises(ValidationError) as exc:
        RecipeIn.model_validate(doc)
    return [e["loc"] for e in exc.value.errors()]


def test_valid_recipe_is_accepted() -> None:
    recipe = RecipeIn.model_validate(
        recipe_doc(servings=4, steps=["Cook."], ingredients=[line("rice", 200, "g")])
    )
    assert recipe.servings == 4
    assert recipe.ingredients[0].quantity == Decimal(200)


def test_missing_macro_is_rejected_and_named() -> None:
    doc = recipe_doc()
    del doc["protein_g"]
    assert ("protein_g",) in error_locs(doc)


@pytest.mark.parametrize("field", ["kcal", "protein_g", "carbs_g", "fat_g"])
def test_negative_macro_is_rejected(field: str) -> None:
    assert (field,) in error_locs(recipe_doc(**{field: -1}))


@pytest.mark.parametrize("servings", [0, -2, 1.5])
def test_invalid_servings_are_rejected(servings: float) -> None:
    assert ("servings",) in error_locs(recipe_doc(servings=servings))


def test_empty_steps_are_rejected() -> None:
    assert ("steps",) in error_locs(recipe_doc(steps=[]))


def test_blank_step_is_rejected() -> None:
    assert ("steps", 1) in error_locs(recipe_doc(steps=["Cook.", "   "]))


def test_empty_ingredients_are_rejected() -> None:
    assert ("ingredients",) in error_locs(recipe_doc(ingredients=[]))


def test_blank_name_is_rejected() -> None:
    assert ("name",) in error_locs(recipe_doc(name="  "))


@pytest.mark.parametrize("minutes", [-1, 2.5])
def test_invalid_times_are_rejected(minutes: float) -> None:
    assert ("prep_time_min",) in error_locs(recipe_doc(prep_time_min=minutes))


def test_quantity_with_unit() -> None:
    recipe = RecipeIn.model_validate(
        recipe_doc(ingredients=[line("Chickpeas", 400, "g", prep_note="drained")])
    )
    got = recipe.ingredients[0]
    assert (got.name, got.quantity, got.unit, got.prep_note) == (
        "chickpeas",
        Decimal(400),
        "g",
        "drained",
    )


def test_ingredient_to_taste() -> None:
    recipe = RecipeIn.model_validate(recipe_doc(ingredients=[line("salt")]))
    assert recipe.ingredients[0].quantity is None
    assert recipe.ingredients[0].unit is None
    assert recipe.ingredients[0].optional is False


def test_quantity_without_unit_is_rejected() -> None:
    assert ("ingredients", 0) in error_locs(recipe_doc(ingredients=[line("eggs", 2)]))


def test_unit_without_quantity_is_rejected() -> None:
    assert ("ingredients", 0) in error_locs(recipe_doc(ingredients=[line("eggs", unit="piece")]))


@pytest.mark.parametrize("quantity", [0, -1])
def test_non_positive_quantity_is_rejected(quantity: float) -> None:
    locs = error_locs(recipe_doc(ingredients=[line("eggs", quantity, "piece")]))
    assert ("ingredients", 0, "quantity") in locs


def test_blank_ingredient_name_is_rejected() -> None:
    assert ("ingredients", 0, "name") in error_locs(recipe_doc(ingredients=[line("   ")]))


@pytest.mark.parametrize("field", ["protein_per_serving", "total_time_min", "id"])
def test_derived_and_server_fields_are_not_accepted(field: str) -> None:
    assert (field,) in error_locs(recipe_doc(**{field: 1}))


def test_order_and_duplicates_are_kept() -> None:
    lines = [line("flour", 200, "g"), line("butter", 100, "g"), line("Flour", 1, "tbsp")]
    recipe = RecipeIn.model_validate(recipe_doc(ingredients=lines))
    assert [i.name for i in recipe.ingredients] == ["flour", "butter", "flour"]


# --- decimals are JSON numbers ---------------------------------------------------


def _non_null(prop: dict) -> dict:
    """The non-null branch of an ``X | None`` property schema, without title and description."""
    if "anyOf" in prop:
        (prop,) = [b for b in prop["anyOf"] if b.get("type") != "null"]
    return {k: v for k, v in prop.items() if k not in ("title", "description")}


def test_recipe_decimals_are_json_numbers() -> None:
    schema = RecipeIn.model_json_schema()
    for field in ("kcal", "protein_g", "carbs_g", "fat_g"):
        assert _non_null(schema["properties"][field]) == {
            "type": "number",
            "minimum": 0,
            "maximum": 999999.9,
        }, field
    line_props = schema["$defs"]["IngredientLineIn"]["properties"]
    assert _non_null(line_props["quantity"]) == {"type": "number", "exclusiveMinimum": 0}


def test_list_bounds_are_json_numbers() -> None:
    props = RecipeListParams.model_json_schema()["properties"]
    for macro in ("kcal", "protein", "carbs", "fat"):
        for side in ("min", "max"):
            assert _non_null(props[f"{side}_{macro}_per_serving"]) == {"type": "number"}


def test_float_parses_to_exact_decimal() -> None:
    recipe = RecipeIn.model_validate(
        recipe_doc(protein_g=12.3, ingredients=[line("rice", 0.1, "kg")])
    )
    assert recipe.protein_g == Decimal("12.3")
    assert recipe.ingredients[0].quantity == Decimal("0.1")
    assert RecipeListParams(min_fat_per_serving=2.2).min_fat_per_serving == Decimal("2.2")


# --- patches ---------------------------------------------------------------------


def patch_error_locs(data: dict) -> list[tuple]:
    with pytest.raises(ValidationError) as exc:
        RecipePatch.model_validate(data)
    return [e["loc"] for e in exc.value.errors()]


def test_patch_keeps_only_the_fields_sent() -> None:
    patch = RecipePatch.model_validate({"name": " Weeknight dal ", "protein_g": 12.3})
    assert patch.model_dump(exclude_unset=True) == {
        "name": "Weeknight dal",
        "protein_g": Decimal("12.3"),
    }


@pytest.mark.parametrize("field", ["description", "prep_time_min", "cook_time_min"])
def test_patch_null_clears_optional_fields(field: str) -> None:
    patch = RecipePatch.model_validate({field: None})
    assert patch.model_dump(exclude_unset=True) == {field: None}


@pytest.mark.parametrize(
    "field", ["name", "servings", "steps", "ingredients", "kcal", "protein_g", "carbs_g", "fat_g"]
)
def test_patch_null_on_required_field_is_rejected(field: str) -> None:
    assert (field,) in patch_error_locs({field: None})


def test_empty_patch_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one field"):
        RecipePatch.model_validate({})


@pytest.mark.parametrize("field", ["protein_per_serving", "id", "updated_at"])
def test_patch_rejects_unknown_fields(field: str) -> None:
    assert (field,) in patch_error_locs({"name": "x", field: 1})


def test_patch_applies_document_rules() -> None:
    assert ("servings",) in patch_error_locs({"servings": 0})
    assert ("steps",) in patch_error_locs({"steps": []})
    assert ("ingredients", 0) in patch_error_locs({"ingredients": [line("eggs", 2)]})


def test_patch_schema_has_no_defaults_and_numbers() -> None:
    schema = RecipePatch.model_json_schema()
    assert "required" not in schema
    assert schema["additionalProperties"] is False
    assert all("default" not in prop for prop in schema["properties"].values())
    assert _non_null(schema["properties"]["protein_g"])["type"] == "number"
