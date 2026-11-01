"""Recipe documents (tool inputs and results), patches and list parameters.

Derived values and server fields are output-only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cookbook.common.fields import (
    DecimalNumber,
    Limit,
    Number,
    Offset,
    OptionalText,
    RequiredText,
    decimal_number,
)
from cookbook.ingredients.normalize import normalize_name

# Totals are numeric(7, 1) in the database.
MacroTotal = decimal_number(ge=0, le=Decimal("999999.9"))
Quantity = decimal_number(gt=0)
Minutes = Annotated[int, Field(ge=0)]
RecipeId = Annotated[int, Field(description="Recipe id, as returned by list_recipes.")]

# Field descriptions shown to clients in the tools' input and output schemas.
_DOC = {
    "name": "Recipe name.",
    "description": "Short summary of the dish.",
    "servings": "How many servings the whole recipe makes.",
    "prep_time_min": "Hands-on preparation time, in minutes.",
    "cook_time_min": "Cooking time, in minutes.",
    "steps": "Method steps in order, one instruction per item.",
    "ingredients": "Ingredient lines in the order they are listed.",
    "kcal": "Energy for the whole recipe in kcal, not per serving.",
    "protein_g": "Protein for the whole recipe in grams, not per serving.",
    "carbs_g": "Carbohydrates for the whole recipe in grams, not per serving.",
    "fat_g": "Fat for the whole recipe in grams, not per serving.",
    "line_name": "Ingredient name. Reuse a name from search_ingredients; stored lowercase.",
    "quantity": "Amount, in `unit`. Give it together with `unit`, or leave both out "
    "for an ingredient added to taste.",
    "unit": "Unit code from list_units, e.g. g, tbsp or clove. Required exactly when "
    "`quantity` is given.",
    "prep_note": "How the ingredient is prepared, e.g. drained or finely chopped.",
    "optional": "True if the dish works without this ingredient, e.g. a garnish. "
    "Not about whether the field can be left out.",
    "per_serving": "Whole-recipe total divided by servings, rounded to one decimal.",
    "total_time_min": "prep_time_min + cook_time_min, a missing one counting as 0; "
    "null when both are missing.",
}
_REPLACES_LIST = " Replaces the whole stored list."
_NULL_CLEARS = " null clears it."

SortKey = Literal[
    "name",
    "-name",
    "created_at",
    "-created_at",
    "total_time",
    "-total_time",
    "kcal_per_serving",
    "-kcal_per_serving",
    "protein_per_serving",
    "-protein_per_serving",
    "carbs_per_serving",
    "-carbs_per_serving",
    "fat_per_serving",
    "-fat_per_serving",
]
# The sort keys without direction, in the order above.
SORT_KEYS = tuple(key for key in get_args(SortKey) if not key.startswith("-"))

_INGREDIENT_NAMES = (
    'Ingredient names as listed by search_ingredients, e.g. ["chicken", "peanut butter"]; '
    "case and surrounding spaces are ignored."
)
# Descriptions of the list_recipes arguments, shared by the tool signature
# and RecipeListParams.
LIST_DOC = {
    "q": "Text to find anywhere in the recipe name, case-insensitively.",
    "max_total_time": "Longest total time (prep + cook) in minutes, inclusive. "
    "A missing prep or cook time counts as 0.",
    **{
        f"{bound}_{macro}_per_serving": f"{label} {name}, in {unit}. Inclusive."
        for macro, name, unit in (
            ("kcal", "energy", "kcal per serving"),
            ("protein", "protein", "grams per serving"),
            ("carbs", "carbohydrates", "grams per serving"),
            ("fat", "fat", "grams per serving"),
        )
        for bound, label in (("min", "Lowest"), ("max", "Highest"))
    },
    "all_ingredients": "Recipes must contain every one of these ingredients. " + _INGREDIENT_NAMES,
    "any_ingredients": "Recipes must contain at least one of these ingredients. "
    + _INGREDIENT_NAMES
    + " Combines with all_ingredients by AND.",
    "sort": "Sort order; a leading - sorts descending. total_time counts a missing "
    "prep or cook time as 0.",
}


class IngredientLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description=_DOC["line_name"])
    quantity: Quantity | None = Field(None, description=_DOC["quantity"])
    unit: str | None = Field(None, description=_DOC["unit"])
    prep_note: OptionalText = Field(None, description=_DOC["prep_note"])
    optional: bool = Field(False, description=_DOC["optional"])

    @field_validator("name")
    @classmethod
    def _normalize(cls, value: str) -> str:
        value = normalize_name(value)
        if not value:
            raise ValueError("ingredient name must not be blank")
        return value

    @field_validator("unit")
    @classmethod
    def _unit_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower() or None

    @model_validator(mode="after")
    def _quantity_needs_unit(self) -> IngredientLineIn:
        if (self.quantity is None) != (self.unit is None):
            raise ValueError("quantity and unit must be given together, or both omitted")
        return self


class RecipeIn(BaseModel):
    """A full recipe document, as sent to ``create_recipe``.

    Derived values (per-serving macros, total time) and server fields (id,
    timestamps) are not accepted.
    """

    model_config = ConfigDict(extra="forbid")

    name: RequiredText = Field(description=_DOC["name"])
    description: OptionalText = Field(None, description=_DOC["description"])
    servings: Annotated[int, Field(gt=0)] = Field(description=_DOC["servings"])
    prep_time_min: Minutes | None = Field(None, description=_DOC["prep_time_min"])
    cook_time_min: Minutes | None = Field(None, description=_DOC["cook_time_min"])
    steps: Annotated[list[RequiredText], Field(min_length=1)] = Field(description=_DOC["steps"])
    ingredients: Annotated[list[IngredientLineIn], Field(min_length=1)] = Field(
        description=_DOC["ingredients"]
    )
    kcal: MacroTotal = Field(description=_DOC["kcal"])
    protein_g: MacroTotal = Field(description=_DOC["protein_g"])
    carbs_g: MacroTotal = Field(description=_DOC["carbs_g"])
    fat_g: MacroTotal = Field(description=_DOC["fat_g"])


def _drop_defaults(schema: dict[str, Any]) -> None:
    # An absent patch field means "unchanged", not its Python default.
    for prop in schema.get("properties", {}).values():
        prop.pop("default", None)


class RecipePatch(BaseModel):
    """Changes to a stored recipe; absent fields stay as they are.

    ``steps`` and ``ingredients`` replace the whole list. ``null`` clears
    ``description``, ``prep_time_min`` and ``cook_time_min``. The other fields
    are typed without ``None``, so an explicit ``null`` fails validation on
    that field, while leaving them out never reaches validation.
    """

    model_config = ConfigDict(extra="forbid", json_schema_extra=_drop_defaults)

    name: RequiredText = Field(None, description=_DOC["name"])  # type: ignore[assignment]
    description: OptionalText = Field(None, description=_DOC["description"] + _NULL_CLEARS)
    servings: Annotated[int, Field(gt=0)] = Field(None, description=_DOC["servings"])  # type: ignore[assignment]
    prep_time_min: Minutes | None = Field(None, description=_DOC["prep_time_min"] + _NULL_CLEARS)
    cook_time_min: Minutes | None = Field(None, description=_DOC["cook_time_min"] + _NULL_CLEARS)
    steps: Annotated[list[RequiredText], Field(min_length=1)] = Field(  # type: ignore[assignment]
        None, description=_DOC["steps"] + _REPLACES_LIST
    )
    ingredients: Annotated[list[IngredientLineIn], Field(min_length=1)] = Field(  # type: ignore[assignment]
        None, description=_DOC["ingredients"] + _REPLACES_LIST
    )
    kcal: MacroTotal = Field(None, description=_DOC["kcal"])
    protein_g: MacroTotal = Field(None, description=_DOC["protein_g"])
    carbs_g: MacroTotal = Field(None, description=_DOC["carbs_g"])
    fat_g: MacroTotal = Field(None, description=_DOC["fat_g"])

    @model_validator(mode="after")
    def _not_empty(self) -> RecipePatch:
        if not self.model_fields_set:
            raise ValueError("patch must change at least one field")
        return self


class IngredientLineOut(BaseModel):
    ingredient_id: int = Field(description="Catalogue id of the ingredient.")
    name: str = Field(description="Catalogue name of the ingredient.")
    quantity: Number | None = Field(description=_DOC["quantity"])
    unit: str | None = Field(description=_DOC["unit"])
    prep_note: str | None = Field(description=_DOC["prep_note"])
    optional: bool = Field(description=_DOC["optional"])


class PerServing(BaseModel):
    kcal_per_serving: Number = Field(description=_DOC["per_serving"])
    protein_per_serving: Number = Field(description=_DOC["per_serving"])
    carbs_per_serving: Number = Field(description=_DOC["per_serving"])
    fat_per_serving: Number = Field(description=_DOC["per_serving"])


class RecipeSummary(PerServing):
    id: int
    name: str
    servings: int
    prep_time_min: int | None
    cook_time_min: int | None
    total_time_min: int | None = Field(description=_DOC["total_time_min"])


class RecipeOut(RecipeSummary):
    description: str | None
    kcal: Number = Field(description=_DOC["kcal"])
    protein_g: Number = Field(description=_DOC["protein_g"])
    carbs_g: Number = Field(description=_DOC["carbs_g"])
    fat_g: Number = Field(description=_DOC["fat_g"])
    steps: list[str]
    ingredients: list[IngredientLineOut]
    created_at: datetime
    updated_at: datetime


class RecipeList(BaseModel):
    items: list[RecipeSummary]
    total: int = Field(description="Recipes matching the filters, ignoring limit and offset.")
    limit: int
    offset: int
    unmatched_ingredients: list[str] = Field(
        description="Requested ingredient names (normalized) that are not in the catalogue, "
        "so they match no recipe. Empty when every name is known."
    )


class RecipeListParams(BaseModel):
    """Arguments of the ``list_recipes`` tool. Bounds are inclusive."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(None, description=LIST_DOC["q"])
    max_total_time: Minutes | None = Field(None, description=LIST_DOC["max_total_time"])
    min_kcal_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["min_kcal_per_serving"]
    )
    max_kcal_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["max_kcal_per_serving"]
    )
    min_protein_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["min_protein_per_serving"]
    )
    max_protein_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["max_protein_per_serving"]
    )
    min_carbs_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["min_carbs_per_serving"]
    )
    max_carbs_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["max_carbs_per_serving"]
    )
    min_fat_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["min_fat_per_serving"]
    )
    max_fat_per_serving: DecimalNumber | None = Field(
        None, description=LIST_DOC["max_fat_per_serving"]
    )
    all_ingredients: list[str] = Field([], description=LIST_DOC["all_ingredients"])
    any_ingredients: list[str] = Field([], description=LIST_DOC["any_ingredients"])
    sort: SortKey = Field("name", description=LIST_DOC["sort"])
    limit: Limit = 50
    offset: Offset = 0

    @field_validator("all_ingredients", "any_ingredients")
    @classmethod
    def _normalize_ingredients(cls, values: list[str]) -> list[str]:
        normalized = [normalize_name(v) for v in values]
        if "" in normalized:
            raise ValueError("ingredient names must not be blank")
        return list(dict.fromkeys(normalized))
