from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from cookbook.common.fields import Limit, Offset, Out

NameQuery = Annotated[
    str | None,
    Field(
        description="Text to find anywhere in the ingredient name, case-insensitively. "
        "Leave it out to page through the whole catalogue."
    ),
]


class IngredientOut(Out):
    id: int
    name: str


class IngredientListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: NameQuery = None
    limit: Limit = 50
    offset: Offset = 0


class IngredientList(BaseModel):
    items: list[IngredientOut]
    limit: int
    offset: int
