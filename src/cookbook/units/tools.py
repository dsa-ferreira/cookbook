"""``list_units``: the fixed unit vocabulary."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from cookbook.common.mcp.errors import tool_errors
from cookbook.common.mcp.session import Sessions
from cookbook.units import service
from cookbook.units.schemas import UnitList

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def register(mcp: MCPServer, sessions: Sessions) -> None:
    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    async def list_units() -> UnitList:
        """List every unit an ingredient line may use.

        Each unit has a code (use it as an ingredient line's `unit`), a
        dimension (mass, volume or count) and its factor to the dimension's
        base unit (g, ml or piece). Units are a fixed vocabulary: a recipe
        with any other unit code is rejected.
        """
        return UnitList(items=await sessions.run(service.list_units))
