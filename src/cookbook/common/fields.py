"""Pydantic field types shared across domains' schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)

_JSON_BOUNDS = {
    "gt": "exclusiveMinimum",
    "ge": "minimum",
    "lt": "exclusiveMaximum",
    "le": "maximum",
}

Limit = Annotated[int, Field(ge=1, le=200)]
Offset = Annotated[int, Field(ge=0)]


def decimal_number(**bounds: Decimal | int) -> Any:
    """A ``Decimal`` input described as a JSON number, with optional ``gt``/``ge``/``lt``/``le``.

    Pydantic's own schema for ``Decimal`` is ``number | string``, which invites
    clients to send strings. Floats still parse from their shortest repr, so
    ``12.3`` becomes ``Decimal("12.3")``.
    """
    schema: dict[str, Any] = {"type": "number"}
    schema.update({_JSON_BOUNDS[k]: float(v) for k, v in bounds.items()})
    return Annotated[Decimal, Field(**bounds), WithJsonSchema(schema)]  # type: ignore[arg-type]


class Out(BaseModel):
    """Base for response models built from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


# The types below call these helpers when the module is imported, so the
# helpers have to be defined first.


def _json_number(value: Decimal) -> int | float:
    """Whole values as ints (``1000``, not ``1000.0``), the rest as floats."""
    return int(value) if value == value.to_integral_value() else float(value)


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


# Decimals are emitted as JSON numbers.
Number = Annotated[
    Decimal, PlainSerializer(_json_number, return_type=int | float, when_used="json")
]
DecimalNumber = decimal_number()
RequiredText = Annotated[str, AfterValidator(_required_text)]
OptionalText = Annotated[str | None, AfterValidator(_optional_text)]
