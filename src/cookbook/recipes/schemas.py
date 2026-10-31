"""Recipe documents (POST/PUT bodies and responses) and list parameters.

Derived values and server fields are output-only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cookbook.common.fields import Limit, Number, Offset, OptionalText, RequiredText
from cookbook.ingredients.normalize import normalize_name

# Totals are numeric(7, 1) in the database.
MacroTotal = Annotated[Decimal, Field(ge=0, le=Decimal("999999.9"))]
Minutes = Annotated[int, Field(ge=0)]


class IngredientLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: Annotated[Decimal, Field(gt=0)] | None = None
    unit: str | None = None
    prep_note: OptionalText = None
    optional: bool = False

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
    """A full recipe document, as sent to POST and PUT.

    Derived values (per-serving macros, total time) and server fields (id,
    timestamps) are not accepted.
    """

    model_config = ConfigDict(extra="forbid")

    name: RequiredText
    description: OptionalText = None
    servings: Annotated[int, Field(gt=0)]
    prep_time_min: Minutes | None = None
    cook_time_min: Minutes | None = None
    steps: Annotated[list[RequiredText], Field(min_length=1)]
    ingredients: Annotated[list[IngredientLineIn], Field(min_length=1)]
    kcal: MacroTotal
    protein_g: MacroTotal
    carbs_g: MacroTotal
    fat_g: MacroTotal


class IngredientLineOut(BaseModel):
    ingredient_id: int
    name: str
    quantity: Number | None
    unit: str | None
    prep_note: str | None
    optional: bool


class PerServing(BaseModel):
    kcal_per_serving: Number
    protein_per_serving: Number
    carbs_per_serving: Number
    fat_per_serving: Number


class RecipeSummary(PerServing):
    id: int
    name: str
    servings: int
    prep_time_min: int | None
    cook_time_min: int | None
    total_time_min: int | None


class RecipeOut(RecipeSummary):
    description: str | None
    kcal: Number
    protein_g: Number
    carbs_g: Number
    fat_g: Number
    steps: list[str]
    ingredients: list[IngredientLineOut]
    created_at: datetime
    updated_at: datetime


class RecipeList(BaseModel):
    items: list[RecipeSummary]
    total: int
    limit: int
    offset: int


SORT_KEYS = (
    "name",
    "created_at",
    "total_time",
    "kcal_per_serving",
    "protein_per_serving",
    "carbs_per_serving",
    "fat_per_serving",
)


class RecipeListParams(BaseModel):
    """Query parameters for ``GET /recipes``. Bounds are inclusive."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    max_total_time: Minutes | None = None
    min_kcal_per_serving: Decimal | None = None
    max_kcal_per_serving: Decimal | None = None
    min_protein_per_serving: Decimal | None = None
    max_protein_per_serving: Decimal | None = None
    min_carbs_per_serving: Decimal | None = None
    max_carbs_per_serving: Decimal | None = None
    min_fat_per_serving: Decimal | None = None
    max_fat_per_serving: Decimal | None = None
    ingredient: list[str] = []
    ingredient_match: Literal["all", "any"] = "all"
    sort: str = "name"
    limit: Limit = 50
    offset: Offset = 0

    @field_validator("ingredient")
    @classmethod
    def _normalize_ingredients(cls, values: list[str]) -> list[str]:
        normalized = [normalize_name(v) for v in values]
        if "" in normalized:
            raise ValueError("ingredient names must not be blank")
        return list(dict.fromkeys(normalized))

    @field_validator("sort")
    @classmethod
    def _sort_key(cls, value: str) -> str:
        if value.removeprefix("-") not in SORT_KEYS:
            raise ValueError(
                "sort must be one of " + ", ".join(SORT_KEYS) + ", optionally prefixed with '-'"
            )
        return value
