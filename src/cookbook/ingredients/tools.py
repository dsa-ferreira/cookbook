"""``search_ingredients``: the ingredient catalogue."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from cookbook.common.fields import Limit, Offset
from cookbook.common.mcp.errors import tool_errors
from cookbook.common.mcp.session import Sessions
from cookbook.ingredients import service
from cookbook.ingredients.schemas import IngredientList, IngredientListParams

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def register(mcp: MCPServer, sessions: Sessions) -> None:
    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    async def search_ingredients(
        q: str | None = None, limit: Limit = 50, offset: Offset = 0
    ) -> IngredientList:
        """Search the ingredient catalogue by name, in name order.

        `q` matches any part of the name, case-insensitively; leave it out to
        page through the whole catalogue. Names are stored normalized
        (trimmed, lowercase). Use these names when writing recipes, so the
        same ingredient isn't stored twice under different spellings.
        """
        params = IngredientListParams(q=q, limit=limit, offset=offset)
        items = await sessions.run(service.search, params)
        return IngredientList(items=items, limit=params.limit, offset=params.offset)
