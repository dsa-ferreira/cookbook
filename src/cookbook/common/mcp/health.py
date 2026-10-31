"""Liveness endpoint. Unauthenticated, and never touches recipe data."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse


def register(mcp: MCPServer) -> None:
    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})
