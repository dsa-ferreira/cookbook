"""Pydantic field types shared across domains' schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer


def _json_number(value: Decimal) -> int | float:
    """Whole values as ints (``1000``, not ``1000.0``), the rest as floats."""
    return int(value) if value == value.to_integral_value() else float(value)


# Decimals are emitted as JSON numbers.
Number = Annotated[
    Decimal, PlainSerializer(_json_number, return_type=int | float, when_used="json")
]

Limit = Annotated[int, Field(ge=1, le=200)]
Offset = Annotated[int, Field(ge=0)]


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


RequiredText = Annotated[str, AfterValidator(_required_text)]
OptionalText = Annotated[str | None, AfterValidator(_optional_text)]


class Out(BaseModel):
    """Base for response models built from ORM objects."""

    model_config = ConfigDict(from_attributes=True)
