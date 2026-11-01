# Proposal

## Why

The cookbook exists to be driven by AI assistants. Its two clients, Claude Code and our Open WebUI instance, both speak MCP natively over Streamable HTTP. The Flask REST API makes each client either hand-roll HTTP calls or go through an adapter. Serving MCP directly removes that layer. Doing it now, while the API is small (three domains), also means future features get built once, as tools, instead of twice.

The switch also fixes a chat-specific problem with the current write contract. `PUT /recipes/{id}` needs the full document, so fixing one step means the model re-sends every step, ingredient line and macro total. That costs tokens and risks dropping data.

## What Changes

- **BREAKING**: Remove the Flask REST API (`/units`, `/ingredients`, `/recipes`, `/recipes/{id}`) and its dependencies (Flask, gunicorn). The MCP server becomes the only interface.
- Add an MCP server at `/mcp`. It uses stateless Streamable HTTP with JSON responses and runs as an ASGI app (Starlette on uvicorn), with seven tools: `list_units`, `search_ingredients`, `list_recipes`, `get_recipe`, `create_recipe`, `update_recipe`, `delete_recipe`. Each tool carries MCP annotations (read-only, idempotent, destructive) and returns structured content.
- **BREAKING**: Replace full-document replace with `update_recipe`, a patch:
  - Absent fields are left unchanged, fields that are present are set, and `null` clears the optional fields.
  - Steps and ingredient lines are replaced as whole lists.
  - The merged document is validated as a full recipe and stored atomically.
- Domain errors (not found, validation) come back as MCP tool errors instead of HTTP 404 and 422. They keep the `error`/`message`/`details` shape so a model can see which field was wrong and retry.
- Keep `/healthz` unauthenticated. Authentication keeps the same named, SHA-256-hashed bearer keys (`COOKBOOK_API_KEYS`), now checked by ASGI middleware. The access log also records the tool name for each tool call.
- The list filter parameter `ingredient` becomes `ingredients` (a list argument instead of a repeated query parameter).
- The container image keeps port 8080 and the migrate-on-start entrypoint, and now runs uvicorn. The README's API section becomes a tool reference with client setup for Claude Code and Open WebUI.

## Capabilities

### New Capabilities
- `mcp-server`: the MCP endpoint itself. Covers the transport, the tool catalogue and its annotations, tool input and output schemas, the tool error shape, server instructions, and the absence of any other data endpoints.

### Modified Capabilities
- `recipes`: every operation is now specified as an MCP tool instead of an HTTP route. Replace becomes patch (`update_recipe`). Rejections are tool errors instead of 422 and 404. The ingredient filter is renamed to `ingredients`. The document shape and the derived values (per-serving macros, total time) don't change.
- `ingredients`: search becomes the `search_ingredients` tool. Get-or-create applies to create and update. A blank name is a tool validation error.
- `units`: listing becomes the `list_units` tool. An unknown unit is a tool validation error.
- `api-auth`: the bearer key protects the MCP endpoint (every path except `/healthz`). The access log records the tool name next to the key name.

## Impact

- **Code**: `src/cookbook/app.py`, `src/cookbook/common/auth.py` and `src/cookbook/common/web/` are rewritten for ASGI. Every domain's `api.py` blueprint is replaced by MCP tool modules. `recipes/service.py` gains `update` (patch), and `recipes/schemas.py` gains a patch model and a JSON-number schema for decimal inputs. The service layer, models, migrations and CLI are otherwise unchanged.
- **Dependencies**: add `mcp` (official Python SDK) and `uvicorn`; remove `flask` and `gunicorn`. Starlette and httpx come in through `mcp`.
- **Tests**: the service, schema, constraint, config, migration and DB tests stay. The Flask client tests (`tests/recipes/test_api_*`, `tests/units/test_api.py`, `tests/common/test_auth.py`, `tests/test_app.py`) are ported to an MCP client and the Starlette test client.
- **Deployment**: the Dockerfile `CMD`, `GUNICORN_CMD_ARGS`, the `make run` target and the README change. Compose, the port, the healthcheck and the environment variables stay the same.
- **Clients**: any existing REST caller breaks. Claude Code and Open WebUI each get their own named key and connect to `http(s)://<host>:8080/mcp`.
