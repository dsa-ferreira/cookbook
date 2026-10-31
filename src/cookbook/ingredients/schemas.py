from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cookbook.common.fields import Limit, Offset, Out


class IngredientOut(Out):
    id: int
    name: str


class IngredientListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    limit: Limit = 50
    offset: Offset = 0


class IngredientList(BaseModel):
    items: list[IngredientOut]
    limit: int
    offset: int
