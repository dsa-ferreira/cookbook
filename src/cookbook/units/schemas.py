from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from cookbook.common.fields import Number, Out


class UnitOut(Out):
    code: str
    dimension: Literal["mass", "volume", "count"]
    to_base: Number


class UnitList(BaseModel):
    items: list[UnitOut]
