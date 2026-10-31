# Tasks

## 1. Dependencies

- [x] 1.1 In `pyproject.toml`, add `mcp` (with a lower bound on the current version, 2.3.0) and `uvicorn`. Keep `flask` and `gunicorn` until group 5, so the app keeps working mid-change. Run `uv lock && uv sync` and verify that `uv run python -c "import mcp.server.mcpserver, uvicorn"` succeeds.

## 2. Schemas and services (framework-free)

- [x] 2.1 Add a `DecimalNumber` field type in `common/fields.py` (a `Decimal` with `WithJsonSchema` type `number`). Use it for `MacroTotal`, `IngredientLineIn.quantity` and the `RecipeListParams` macro bounds. Verify with a `test_schemas` case: the JSON schemas of `RecipeIn` and `RecipeListParams` show those fields as `"type": "number"`, and `12.3` parses to `Decimal("12.3")`.
- [x] 2.2 Rename `RecipeListParams.ingredient` to `ingredients` and update the listing query in `recipes/service.py`. Verify that `tests/recipes/test_list_params.py` (updated) and the listing tests pass.
- [x] 2.3 Add `RecipePatch` to `recipes/schemas.py` (design §7). It forbids extra fields, accepts null only on `description`/`prep_time_min`/`cook_time_min`, and rejects an empty patch. Verify with `test_schemas` cases for each rule.
- [x] 2.4 Add `recipes.service.update(session, recipe_id, patch)`, which merges into the stored document, validates as `RecipeIn` and reuses the replace path atomically. Make `replace` private. Verify with service-level tests:
  - patching one field leaves the steps, lines and totals unchanged;
  - an `ingredients` patch replaces the whole list;
  - `null` clears prep time;
  - an unknown unit in the patch leaves the recipe unchanged and creates no ingredient;
  - an unknown id raises `NotFoundError`;
  - `updated_at` advances.

## 3. MCP server core

- [x] 3.1 Create the `common/mcp/` package:
  - a session helper that runs a sync callable in a worker thread with a session from the app's factory, and always closes it;
  - an error wrapper that maps `ValidationError`, `InvalidInputError`, `NotFoundError` and any other exception to an `isError` `CallToolResult` with the `{"error", "message", "details"?}` body.

  Verify with unit tests of the wrapper: each exception type gives the right code, and `internal_error` contains no exception text.
- [x] 3.2 Rewrite `common/auth.py`. Keep `hash_key`/`match_key`, and replace the Flask hooks with pure ASGI middleware (design §2):
  - `/healthz` is exempt;
  - a missing, bad or unknown key gets a 401 JSON body with `WWW-Authenticate: Bearer`;
  - the key name goes into scope state;
  - one access-log line per request.

  Verify with middleware tests against a dummy ASGI app: 401 cases, pass-through with the key name set, and log lines that contain the name but not the key or the hash.
- [x] 3.3 Rewrite `cookbook/app.py`: `create_app(settings, session_factory=None)` builds `MCPServer` with server instructions, registers `/healthz` as a custom route and each domain's tools, and returns `streamable_http_app()` (stateless, JSON responses, DNS-rebinding protection off) wrapped in the auth middleware. Verify by starting uvicorn locally against compose Postgres (`--factory`). `curl /healthz` returns `{"status":"ok"}`, and `curl -X POST /mcp` without a key returns 401.
- [x] 3.4 Replace the Flask fixtures in `tests/conftest.py` with:
  - `app`: the ASGI app;
  - `http`: a Starlette `TestClient` that sends the test key;
  - `anon_http`;
  - `mcp_client`: an in-process `mcp.Client` bound to the app's `MCPServer` instance and the savepoint session factory;
  - a `call(name, **args)` helper that returns `(is_error, structured)`.

  Port `tests/test_app.py` and `tests/common/test_auth.py` to them. Verify they pass, including:
  - `/healthz` works without a key;
  - `initialize` without a key gets a 401;
  - an unknown key gets a 401 and no recipe is created;
  - `GET /recipes` with a key returns 404;
  - `POST /mcp` with a key does not redirect;
  - `initialize` returns instructions that mention `search_ingredients`, `list_units` and whole-recipe totals.

## 4. Tools per domain

- [x] 4.1 Add `units/tools.py` with a read-only `list_units` tool, and port `tests/units/test_api.py` to `mcp_client`. Verify that the result includes `g`, `ml` and `clove` with their dimensions and factors.
- [x] 4.2 Add `ingredients/tools.py` with a read-only `search_ingredients(q, limit, offset)` tool, and add MCP tests for substring search, name order without `q`, and a `limit` of 201 giving a `validation_error`. Verify that the tests pass.
- [x] 4.3 Add the read tools to `recipes/tools.py`:
  - `get_recipe`;
  - `list_recipes`, with flat arguments as in design §4, building `RecipeListParams`.

  Port `tests/recipes/test_api_list.py` and the read half of `test_api_read_delete.py`. Verify that the filters, `ingredients` with `all`/`any`, normalization, sorting, the default page of 50 out of 60, a `validation_error` for `sort="tastiness"`, and `not_found` on an unknown id all pass.
- [x] 4.4 Add the write tools to `recipes/tools.py`, with annotations as specified:
  - `create_recipe(recipe)`;
  - `update_recipe(recipe_id, changes)`;
  - `delete_recipe(recipe_id)`, returning `{"id", "deleted": true}`.

  Write tool descriptions that state the whole-recipe macro and patch semantics. Port `test_api_create.py` and the delete half of `test_api_read_delete.py`, and replace `test_api_replace.py` with `test_tools_update.py`, which covers every `update_recipe` scenario in `specs/recipes`. Verify that they pass, including:
  - a `validation_error` naming `servings` for 0 servings, both through the SDK's argument validation and through our wrapper;
  - an unknown unit `handful` named in the error;
  - delete keeps "tahini" in the catalogue.
- [x] 4.5 Add a catalogue test. Verify that `tools/list` returns exactly the seven tools, with `readOnlyHint` on the four read tools, `destructiveHint` and `idempotentHint` on `delete_recipe`, `idempotentHint` on `update_recipe`, output schemas on every tool, and `"type": "number"` for `protein_g` in the `create_recipe` input schema.

## 5. Remove Flask and repackage

- [x] 5.1 Delete `*/api.py` and `common/web/` (moving `/healthz` and anything still used into `common/mcp/`), and drop `flask` and `gunicorn` from `pyproject.toml`. Verify that `uv lock`, `make lint` and `make test` all pass, and that `grep -ri flask src tests` finds nothing.
- [x] 5.2 Switch to uvicorn:
  - Dockerfile `CMD`: `uvicorn --factory cookbook.app:create_app --host 0.0.0.0 --port 8080 --proxy-headers`;
  - remove `GUNICORN_CMD_ARGS`;
  - `make run`: the same command, using `BIND`.

  Verify that `make image && docker compose up -d --build` reports the `cookbook` container healthy, and that `curl :8080/healthz` returns ok.
- [x] 5.3 Rewrite the README's API section as a tool reference:
  - each tool's arguments, result and an example, plus the error codes;
  - client setup for Claude Code (`claude mcp add --transport http ... --header`) and Open WebUI (an MCP Streamable HTTP server with a bearer key);
  - one key per client;
  - debugging with MCP Inspector, plus one raw `curl` `tools/call` example.

  Update the Running and Configuration sections for uvicorn. Verify that the documented `curl` example works against the compose stack.

## 6. Integration check

- [x] 6.1 Run an end-to-end check against the compose stack with a fresh key. Register the server in Claude Code with `claude mcp add --transport http`, then: list units, search ingredients, create a recipe, update one step, list with a protein filter and delete it. Verify that each call succeeds, and that the access log shows the key name with each tool name and never the key.
- [x] 6.2 Run `openspec validate replace-http-api-with-mcp --strict`, `make lint` and `make test`, and verify that all three pass.

## Workflow follow-up

- Connect Open WebUI to the deployed server with its own key and try a recipe search from a chat.
- Archive the change with `/opsx:archive` once it is deployed and both clients work.
