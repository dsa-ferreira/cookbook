from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from cookbook.common.fields import Number, Out


class UnitOut(Out):
    code: str = Field(description="Use as an ingredient line's `unit`.")
    dimension: Literal["mass", "volume", "count"]
    to_base: Number = Field(
        description="How many of the dimension's base unit (g, ml or piece) one of "
        "this unit is, e.g. 15 for tbsp."
    )


class UnitList(BaseModel):
    items: list[UnitOut]
