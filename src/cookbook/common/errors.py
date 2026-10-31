"""Domain errors raised by services. Tools report them as tool errors (``common.mcp.errors``)."""

from __future__ import annotations

from typing import Any


class NotFoundError(Exception):
    """The requested object does not exist (``not_found``)."""


class InvalidInputError(Exception):
    """Input that passed schema validation but is still unacceptable (``validation_error``).

    ``details`` uses the same shape as pydantic error details, so clients
    handle both kinds of validation error the same way.
    """

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []
