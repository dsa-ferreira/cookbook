"""The cookbook's ``MCPServer``: strict arguments, one error body, logged rejections."""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import CallToolResult
from pydantic import ValidationError

from cookbook.common.mcp.errors import error_result, to_error_result

log = logging.getLogger("cookbook.mcp")


class CookbookServer(MCPServer):
    def add_tool(self, fn: Any, name: str | None = None, **kwargs: Any) -> None:
        """Register a tool whose input schema forbids undeclared arguments.

        ``call_tool`` enforces the flag, so the advertised schema and the
        check use the same property list.
        """
        super().add_tool(fn, name=name, **kwargs)
        tool = self._tool_manager.get_tool(name or fn.__name__)
        if tool is not None:
            tool.parameters["additionalProperties"] = False

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        """Run a tool, rejecting bad arguments with a ``validation_error`` body.

        Arguments the tool doesn't declare are rejected before it runs; the
        SDK would drop them silently. Arguments that fail the input schema
        get the ``{"error", "message", "details"}`` body instead of the SDK's
        plain text, with locations such as ``recipe.servings``. Every
        ``validation_error``, from here or from the tool body, is logged
        without argument values. Crashes and unknown tools keep the SDK's
        handling.
        """
        result = await self._checked_call(name, arguments or {}, context)
        if _is_validation_error(result):
            log.warning(
                "tool %s rejected: args=%s details=%s",
                name,
                sorted(arguments or {}),
                result.structured_content.get("details"),
            )
        return result

    async def _checked_call(self, name: str, arguments: dict[str, Any], context: Any) -> Any:
        undeclared = self._undeclared_arguments(name, arguments)
        if undeclared:
            return _unknown_arguments_result(undeclared)
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            if isinstance(exc, UnexpectedToolError) or not isinstance(
                exc.__cause__, ValidationError
            ):
                raise
            result: CallToolResult = to_error_result(exc.__cause__)
            return result

    def _undeclared_arguments(self, name: str, arguments: dict[str, Any]) -> list[str]:
        """Argument names not in the tool's input schema, in request order."""
        tool = self._tool_manager.get_tool(name)
        if tool is None:
            return []
        declared = tool.parameters.get("properties", {})
        return [key for key in arguments if key not in declared]


def _unknown_arguments_result(names: list[str]) -> CallToolResult:
    # Shaped like Pydantic's extra_forbidden, as nested models report it.
    details = [
        {"type": "extra_forbidden", "loc": [key], "msg": "Extra inputs are not permitted"}
        for key in names
    ]
    return error_result("validation_error", "unknown argument: " + ", ".join(names), details)


def _is_validation_error(result: Any) -> bool:
    return (
        isinstance(result, CallToolResult)
        and result.is_error
        and isinstance(result.structured_content, dict)
        and result.structured_content.get("error") == "validation_error"
    )
