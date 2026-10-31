"""Domain errors raised by services. The API maps them to JSON responses."""

from __future__ import annotations

from typing import Any


class NotFoundError(Exception):
    """The requested object does not exist (404)."""


class InvalidInputError(Exception):
    """Input that passed schema validation but is still unacceptable (422).

    ``details`` uses the same shape as pydantic error details, so clients
    handle both kinds of 422 the same way.
    """

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []
