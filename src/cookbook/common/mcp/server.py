"""The cookbook's ``MCPServer``: argument errors use the same body as tool errors."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import CallToolResult
from pydantic import ValidationError

from cookbook.common.mcp.errors import to_error_result


class CookbookServer(MCPServer):
    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        """Report arguments that fail the input schema as ``validation_error``.

        The SDK validates arguments before the tool body runs and reports a
        failure as plain text. Here it gets the ``{"error", "message",
        "details"}`` body instead, with locations such as ``recipe.servings``.
        Crashes and unknown tools keep the SDK's handling.
        """
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            if isinstance(exc, UnexpectedToolError) or not isinstance(
                exc.__cause__, ValidationError
            ):
                raise
            result: CallToolResult = to_error_result(exc.__cause__)
            return result
