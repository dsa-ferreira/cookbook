# Design

## Context

The app is a Flask factory (`cookbook.app:create_app`) served by gunicorn. Flask is confined to a thin layer:

- **Flask-only code:** the domain blueprints (`*/api.py`) and `common/web/`, which holds the JSON errors, query and body parsing, and the per-request session on `flask.g`.
- **Framework-free code:** the services (`recipes/service.py`, `ingredients/service.py`, `units/service.py`) take a plain SQLAlchemy `Session` and Pydantic models, and raise `NotFoundError`/`InvalidInputError` from `common/errors.py`.
- **Auth:** `common/auth.py` mixes framework-free key matching (`hash_key`, `match_key`) with Flask hooks.

Everything below the blueprints survives as it is. See proposal.md for why we're switching, and `specs/` for the behaviour.

Constraints:
- Single container on a homelab, behind a reverse proxy, port 8080.
- Two clients: Claude Code (HTTP transport with a static header) and Open WebUI (native MCP with a bearer key).
- Services and the database layer are synchronous (SQLAlchemy and psycopg 3, sync).

## Goals / Non-Goals

**Goals:**
- Keep the transport layer as thin as the blueprints were, so tools are one-line adapters over the services.
- Reuse the existing Pydantic schemas for tool input and output schemas, so validation rules live in one place.
- Keep the test strategy (one testcontainers Postgres, rollback per test) and make tool tests as cheap as the Flask client tests were.

**Non-Goals:**
- OAuth or any per-user identity beyond named keys. claude.ai remote connectors stay unsupported.
- MCP resources, prompts, sampling or server-to-client notifications.
- Async database access. The services stay sync.
- Patching individual steps or ingredient lines inside `update_recipe`.

## Decisions

### 1. `MCPServer` from the official `mcp` SDK (2.x), served as its Starlette app

Build an `MCPServer("cookbook", instructions=...)` instance (mcp 2.x renamed v1's `FastMCP` to `MCPServer`, in `mcp.server.mcpserver`). Use `mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=...)` as the ASGI application; in 2.x these transport flags are arguments to that call rather than to the constructor, and the default path is already `/mcp`. Register `/healthz` with `@mcp.custom_route`, so there is one Starlette app and the SDK's lifespan (which runs the session manager) is wired correctly without hand-mounting.

`create_app(settings, session_factory=None)` keeps its signature and returns the ASGI app wrapped in the auth middleware. Uvicorn runs it with `--factory`.

- *Alternative: FastAPI with the MCP server mounted.* That only pays off if REST stays, and it doesn't.
- *Alternative: the standalone `fastmcp` package.* It has more features (built-in bearer providers), but it's a second vendor. The official SDK covers everything we need.
- *Alternative: mounting `streamable_http_app()` inside our own Starlette app.* That works, but it means forwarding the SDK lifespan by hand, which is a common source of "task group not initialized" errors.

**Stateless with JSON responses**: no session state survives a restart or needs to be shared, and SSE buys nothing because no tool streams progress. It also makes every request independently testable.

**DNS-rebinding protection**: the SDK turns this on automatically for localhost hosts. It protects unauthenticated local servers, but would reject our reverse-proxied hostname. We pass explicit transport security with it disabled. The bearer key is the access control.

### 2. Bearer auth as pure ASGI middleware

`common/auth.py` keeps `hash_key` and `match_key` unchanged and replaces the Flask hooks with a small ASGI middleware class:

- **Exempt path:** it skips `/healthz` (and lifespan scopes).
- **Missing or unknown key:** it answers 401 with `{"error": "unauthorized", "message": "a valid API key is required"}` and `WWW-Authenticate: Bearer`.
- **Valid key:** it puts the key name in `scope["state"]["api_key_name"]`.
- **Access log:** it logs `METHOD path status key=<name>` once per HTTP request on `cookbook.access`, followed by `tool=<name>` for each `tools/call` in the request. To get the tool name it reads the JSON-RPC body (up to the SDK's 4 MiB request limit) and replays it to the app. The name is client input, so anything that isn't a plain identifier is logged as `?`. Reading it from the tool's `Context` instead would mean adding a context parameter to every tool, and the in-process test client has no HTTP request to read.

It is pure ASGI rather than Starlette's `BaseHTTPMiddleware`, which has known problems with streaming responses and background tasks.

- *Alternative: the SDK's `token_verifier` with `AuthSettings`.* This makes the server an OAuth resource server: it requires an issuer URL and publishes protected-resource metadata, which would make clients try OAuth discovery. That's the wrong model for static keys.

### 3. Tools are thin async adapters that run the sync services in a worker thread

New modules `units/tools.py`, `ingredients/tools.py` and `recipes/tools.py` each expose `register(mcp)`, replacing `api.py`. Each tool:

1. Is declared `async` with typed parameters, a docstring (which becomes the tool description) and `ToolAnnotations`.
2. Calls `anyio.to_thread.run_sync` on a sync function. That function opens a session from the app's session factory, calls the service, and closes the session, rolling back if nothing was committed.
3. Returns the service's Pydantic model, so `MCPServer` emits `structuredContent`, an `outputSchema` and JSON text.

Running in a thread keeps sync DB calls off the event loop (`MCPServer` would otherwise call a sync tool inline). A shared `common/mcp/` package holds the session helper and the error wrapper (§5), replacing `common/web/`. Each domain's `register(mcp, sessions)` receives the session helper that `create_app` builds from its session factory, so tests can still inject the savepoint-bound factory.

`delete_recipe` returns `{"id": <id>, "deleted": true}`, because a tool has to return something the model can read.

### 4. Tool signatures

- **`create_recipe(recipe: RecipeIn)`** and **`update_recipe(recipe_id: int, changes: RecipePatch)`**: one nested document argument each, so the existing models are the schema and nothing is duplicated.
- **`list_recipes(q=None, max_total_time=None, min_/max_* bounds…, ingredients=[], ingredient_match="all", sort="name", limit=50, offset=0)`**: flat optional arguments. Models fill these in well, and smaller models in Open WebUI handle flat optional arguments better than an optional nested object. The tool builds `RecipeListParams(...)` from them, so validation stays in the model. `RecipeListParams.ingredient` is renamed to `ingredients`.
- **`search_ingredients(q=None, limit=50, offset=0)`**, **`get_recipe(recipe_id: int)`**, **`list_units()`**.

Tool descriptions carry the domain hints the model needs: macros are whole-recipe totals, a unit is required whenever a quantity is given, patches replace lists wholesale, and `null` clears optional fields. The server `instructions` cover the workflow: search ingredients first and use `list_units` codes.

### 5. Errors become `isError` results with the old body shape

A decorator around each tool's body catches errors and returns a `CallToolResult(isError=True)`. Its text content is the same JSON body as before (`{"error", "message", "details"?}`), and the same dict goes in `structuredContent`:

| Exception | Error code |
| --- | --- |
| `pydantic.ValidationError` | `validation_error`, with details produced the same way as today (round-tripped through `exc.json()`) |
| `InvalidInputError` | `validation_error`, with its details |
| `NotFoundError` | `not_found` |
| anything else | `internal_error`, logged with a traceback and returned without internals |

Some argument validation happens inside `MCPServer` before our function runs, such as a wrong type for a top-level parameter or a nested model (`recipe`, `changes`) that fails its rules. The SDK reports those as plain text without an error code, which would not meet the spec's `validation_error` requirement for cases like 0 servings or an empty patch. A small `MCPServer` subclass (`common/mcp/server.py`) overrides the public `call_tool`: when the SDK raises `ToolError` caused by a `ValidationError`, it returns the same body as above, with locations prefixed by the argument name (e.g. `recipe.servings`). Crashes and unknown tools keep the SDK's handling. Because argument errors are reported this way, tool parameters can carry their real bounds (e.g. `limit` ≤ 200) in the input schema.

### 6. Decimal inputs as JSON numbers

`MacroTotal`, the ingredient `quantity` and the list bounds are `Decimal`. In JSON Schema mode, Pydantic renders them as `number | string` (with a pattern). We annotate them with `WithJsonSchema({"type": "number", ...bounds})`, a shared `DecimalNumber` type in `common/fields.py`. Pydantic still parses incoming floats into `Decimal` from their shortest repr (`12.3` stays `Decimal("12.3")`), so stored values stay exact to the column's one decimal place. Output already serializes via `Number`.

### 7. Patch model and merge

`RecipePatch` uses `extra="forbid"` and has every `RecipeIn` field optional:

- **Nullable fields:** `description`, `prep_time_min` and `cook_time_min` are typed `X | None`.
- **Other fields:** they are typed non-nullable in the schema, and a validator rejects explicit `None` using `model_fields_set`.
- **Empty patch:** a model validator rejects a patch where `model_fields_set` is empty.

`recipes.service.update(session, recipe_id, patch)`:

1. Loads the current recipe.
2. Converts it to a `RecipeIn`-shaped dict (lines as `name`/`quantity`/`unit`/`prep_note`/`optional`).
3. Overlays `patch.model_dump(exclude_unset=True)` and validates the result as `RecipeIn`.
4. Hands it to the existing replace path, in one transaction.

`replace` becomes a private helper, so the delete-children-first ordering and the `updated_at` bump are reused as they are. Validation errors from the merged document use `RecipeIn` field locations, which are the same field names the client sent.

- *Alternative: JSON Merge Patch (RFC 7396) on raw dicts.* It's the same semantics, but it gives up typed schemas in `tools/list`.
- *Alternative: per-line operations (add, remove, move a step).* That's more surface to specify and test. It's deferred (see Non-Goals).

### 8. Serving and packaging

- **Server:** uvicorn replaces gunicorn: one process, no workers. That's enough for two clients on a homelab, and it's what the SDK's stateless mode expects.
- **Dockerfile:** `CMD ["uvicorn", "--factory", "cookbook.app:create_app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]`, and `GUNICORN_CMD_ARGS` is removed.
- **Makefile:** `make run` uses the same command with `BIND` split into host and port.
- **Unchanged:** compose, the healthcheck, the entrypoint (migrate first) and the environment variables.

### 9. Tests

- **Fixtures:** `conftest.py` swaps the Flask fixtures for `app` (the ASGI app from `create_app(settings, session_factory)`), `http` (a Starlette `TestClient` for `/healthz`, 401s and the removed REST paths) and `mcp_client`, an async fixture that connects an `mcp.Client` to the `MCPServer` instance in-process (2.x's `Client` accepts a server object directly). The in-memory client skips the HTTP auth middleware, so auth is tested only through `http`, and every tool test exercises the full tool path with the rollback-per-test database.
- **Test helper:** `call(name, **args)` returns `(is_error, structured)`, so ported tests stay as short as the Flask versions.
- **Unchanged tests:** `test_schemas`, `test_constraints`, `test_list_params` (updated for the `ingredients` rename), `test_config`, `test_db`, `test_migrations` and the ingredient and unit service tests.
- **Async:** `anyio`'s pytest plugin (shipped with anyio) runs the async tests, so no new test dependency is needed.

## Risks / Trade-offs

- [**MCP SDK API churn.** The SDK has already had one breaking major (v1 `FastMCP` → v2 `MCPServer`), and transport flags and the in-process client moved with it.] → Pin a lower bound on the version we build against (`mcp>=2.3.0`). Keep the SDK touchpoints in `app.py`, `common/mcp/` and `conftest.py`.
- [**No more `curl` for manual checks.**] → Document using MCP Inspector (`npx @modelcontextprotocol/inspector`) against `/mcp` with the bearer header, plus one raw `curl` `tools/call` example in the README.
- [**Reverse proxy path or redirect quirks.** `/mcp` and `/mcp/` may redirect, and some clients drop the auth header on redirect.] → Document the exact URL `/mcp`. Add a test that `POST /mcp` with a valid key does not redirect.
- [**Open WebUI with small local models** may send numbers as strings or skip the nested `recipe` object.] → Lax Pydantic parsing already accepts numeric strings for `Decimal` and `int`. Tool errors name the field so the model can retry. The flat `list_recipes` arguments cover the most common call.
- [**Breaking change for any REST caller.**] → There are only two known clients and both move to MCP. A rollback is a redeploy of the previous image tag; the schema is unchanged, so it's safe.
- [**Merge-then-validate error locations** point at the merged document, not the patch.] → The field names are the same. For list items, the location includes the index into the patched list, since lists are replaced as a whole.

## Migration Plan

1. Build and push the new image (`make push`). The database needs no migration.
2. Generate a key for each client (`make apikey NAME=claude-code`, `make apikey NAME=openwebui`), add both to `COOKBOOK_API_KEYS`, and redeploy.
3. Register the server in each client:
   - Claude Code: `claude mcp add --transport http cookbook https://<host>/mcp --header "Authorization: Bearer <key>"`.
   - Open WebUI: add an MCP (Streamable HTTP) tool server with the URL and the bearer key.
4. Rollback: redeploy the previous image tag. Data and keys work with both versions.
