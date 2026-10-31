"""Tool errors: an ``isError`` result whose body is ``{"error", "message", "details"?}``.

The body goes both in ``structuredContent`` and, as JSON, in the text
content, so clients that ignore structured content still see the field
that was wrong and can retry.
"""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from cookbook.common.errors import InvalidInputError, NotFoundError

log = logging.getLogger(__name__)


def error_result(
    code: str, message: str, details: list[dict[str, Any]] | None = None
) -> CallToolResult:
    body: dict[str, Any] = {"error": code, "message": message}
    if details is not None:
        body["details"] = details
    return CallToolResult(
        is_error=True,
        content=[TextContent(type="text", text=json.dumps(body))],
        structured_content=body,
    )


def to_error_result(exc: Exception) -> CallToolResult:
    if isinstance(exc, ValidationError):
        # Round-trip through JSON: ctx may hold exception objects.
        details = json.loads(exc.json(include_url=False, include_input=False))
        return error_result("validation_error", "validation failed", details)
    if isinstance(exc, InvalidInputError):
        return error_result("validation_error", exc.message, exc.details)
    if isinstance(exc, NotFoundError):
        return error_result("not_found", str(exc) or "not found")
    log.error("unhandled error in tool", exc_info=exc)
    return error_result("internal_error", "internal server error")


def tool_errors[**P, T](fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Turn exceptions raised by an async tool into tool error results.

    ``functools.wraps`` keeps the signature and annotations, which the SDK
    reads to build the tool's input and output schemas.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            return to_error_result(exc)  # type: ignore[return-value]

    return wrapper
