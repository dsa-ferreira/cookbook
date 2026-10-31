"""ASGI application factory: the MCP server, its tools, health and auth.

Run with ``uvicorn --factory cookbook.app:create_app``.
"""

from __future__ import annotations

import logging

from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import ASGIApp

from cookbook.common import db
from cookbook.common.auth import ApiKeyMiddleware
from cookbook.common.config import Settings, get_settings
from cookbook.common.mcp import health
from cookbook.common.mcp.server import CookbookServer
from cookbook.common.mcp.session import Sessions
from cookbook.ingredients import tools as ingredient_tools
from cookbook.recipes import tools as recipe_tools
from cookbook.units import tools as unit_tools

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

INSTRUCTIONS = """\
A cookbook of recipes, each with ordered steps, ingredient lines and macronutrients.

- Before creating or updating a recipe, call search_ingredients and reuse the catalogue's \
names, so one ingredient isn't stored under several spellings.
- Units come from a fixed vocabulary: call list_units and use its codes. Give a unit exactly \
when a line has a quantity; leave both out for "to taste".
- kcal, protein_g, carbs_g and fat_g are whole-recipe totals, not per serving. Per-serving \
values and total time are computed by the server.
- update_recipe takes a patch: send only the fields to change. steps and ingredients replace \
the whole list, and null clears description, prep_time_min or cook_time_min.
"""


def build_server(session_factory: sessionmaker[Session]) -> CookbookServer:
    """The MCP server with every domain's tools and ``/healthz``."""
    server = CookbookServer("cookbook", instructions=INSTRUCTIONS)
    sessions = Sessions(session_factory)
    health.register(server)
    for domain in (unit_tools, ingredient_tools, recipe_tools):
        domain.register(server, sessions)
    return server


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> ASGIApp:
    """Build the app. Raises ``ConfigError`` if the environment is invalid."""
    settings = settings or get_settings()
    # Before MCPServer, whose own basicConfig then leaves ours in place.
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    # Stateless mode logs a session start/stop line per request.
    logging.getLogger("mcp").setLevel(logging.WARNING)

    if session_factory is None:
        session_factory = db.make_session_factory(db.make_engine(settings.database_url))

    server = build_server(session_factory)
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        # Rebinding protection guards unauthenticated local servers and would
        # reject the reverse proxy's hostname; the bearer key is the guard here.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return ApiKeyMiddleware(app, settings.api_keys)
