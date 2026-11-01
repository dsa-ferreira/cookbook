# cookbook

A small recipe store served as an [MCP](https://modelcontextprotocol.io)
server, meant to be driven by AI assistants (Claude Code, Open WebUI). It
keeps recipes with ordered steps, structured ingredient lines, timing and
whole-recipe macronutrients, and derives per-serving macros and total time.
The MCP Python SDK (Streamable HTTP, stateless, JSON responses) on uvicorn,
with SQLAlchemy on Postgres. Every path except `/healthz` needs an API key.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), Docker (or Podman with
`docker` emulation) and `make`.

```sh
make install                 # uv sync: .venv with dev dependencies
docker compose up -d postgres
```

## Configuration

All configuration comes from environment variables. The service validates
them at startup and refuses to start if something is wrong, including when no
API keys are configured. Error messages never contain key hashes.

| Variable | Required | Example | Description |
| --- | --- | --- | --- |
| `COOKBOOK_DATABASE_URL` | yes | `postgresql://cookbook:cookbook@127.0.0.1:5432/cookbook` | Postgres URL. `postgresql://` is accepted and run through psycopg 3 |
| `COOKBOOK_API_KEYS` | yes (not for `migrate`) | `{"diogo": "9f86d0…", "partner": "60303a…"}` | JSON object mapping a key name to the SHA-256 hex digest of that key |

Only hashes go in configuration. To revoke a key, remove its entry and
restart.

### Generating a key

```sh
make apikey NAME=diogo
```

```
API key for 'diogo' (shown once; store it now):
Xq3…the key…

Add this entry to the COOKBOOK_API_KEYS JSON object:
"diogo": "9f86d0…the hash…"
```

Give the key to its owner (it is not shown again) and add the entry to
`COOKBOOK_API_KEYS`. Clients send it as `Authorization: Bearer <key>`.

Generate **one key per client** (`make apikey NAME=claude-code`, `make apikey
NAME=openwebui`), so the access log tells them apart and you can revoke one
without the other. Each request is logged with the key name, never the key,
plus the tool name for tool calls:

```
INFO cookbook.access: POST /mcp 200 key=openwebui tool=delete_recipe
```

## Running

### With docker compose

```sh
cp .env.example .env          # then put your entries in COOKBOOK_API_KEYS
docker compose up -d --build
curl http://localhost:8080/healthz
```

The `cookbook` container applies migrations (`cookbook migrate`) and then
starts uvicorn (one process) on port 8080, with `--proxy-headers` so it
trusts `X-Forwarded-*` from a reverse proxy. Data lives in the `pgdata`
volume. The MCP endpoint is `http://<host>:8080/mcp`.

### Locally

```sh
export COOKBOOK_DATABASE_URL=postgresql://cookbook:cookbook@127.0.0.1:5432/cookbook
export COOKBOOK_API_KEYS='{"diogo": "<hash>"}'
make migrate
make run                      # uvicorn on 0.0.0.0:8080 (override with BIND=host:port)
```

## Testing

```sh
make lint
make test
```

Tests start a throwaway `postgres:17` container with testcontainers, apply
the migrations once and roll back every test's transaction. They need a
working Docker or Podman socket (`DOCKER_HOST`). Ryuk is disabled by default
because rootless Podman can't run it; set `TESTCONTAINERS_RYUK_DISABLED=false`
to turn it back on.

## Other make targets

| Target | What it does |
| --- | --- |
| `make format` | `ruff check --fix` + `ruff format` |
| `make image` | build `cookbook:<version>` and `cookbook:latest` |
| `make push` | build, then push both tags to `album.lan` |

## Connecting clients

The endpoint is exactly `/mcp`. `/mcp/` answers with a redirect, and some
clients drop the `Authorization` header when they follow one.

### Claude Code

```sh
claude mcp add --transport http cookbook https://<host>/mcp \
  --header "Authorization: Bearer <claude-code key>"
```

### Open WebUI

In Open WebUI's tool server settings, add a server of type **MCP
(Streamable HTTP)** with the URL `https://<host>/mcp` and bearer
authentication with the `openwebui` key.

### Debugging

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) lists the
tools and lets you call them by hand:

```sh
npx @modelcontextprotocol/inspector
```

Choose the **Streamable HTTP** transport, enter `http://localhost:8080/mcp`
and add an `Authorization: Bearer <key>` header.

The endpoint is stateless, so a single `curl` can call a tool without
initializing first:

```sh
curl http://localhost:8080/mcp \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
       "params": {"name": "list_units", "arguments": {}}}'
# {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"..."}],
#  "structuredContent":{"items":[{"code":"can","dimension":"count","to_base":1},...]},
#  "isError":false}}
```

`curl http://localhost:8080/healthz` needs no key and returns
`{"status": "ok"}`.

## Tools

Every result is returned as `structuredContent` (matching the tool's output
schema) and as the same JSON in a text block. The server's instructions
tell clients to search ingredients before writing, to take unit codes from
`list_units`, and that macros are whole-recipe totals.

| Tool | Effect | Annotations |
| --- | --- | --- |
| `list_units` | unit vocabulary | read-only |
| `search_ingredients` | ingredient catalogue | read-only |
| `list_recipes` | find recipes | read-only |
| `get_recipe` | one full recipe | read-only |
| `create_recipe` | add a recipe | — |
| `update_recipe` | patch a recipe | idempotent |
| `delete_recipe` | remove a recipe | destructive, idempotent |

### Errors

A failed call is a normal result with `isError: true`, never a protocol
error. Its structured content (and text) is:

```json
{"error": "validation_error", "message": "validation failed", "details": [{"type": "greater_than", "loc": ["recipe", "servings"], "msg": "Input should be greater than 0", "ctx": {"gt": 0}}]}
```

Arguments a tool doesn't declare are rejected too, before the tool runs
(every input schema has `additionalProperties: false`). Each one gets a
details entry:

```json
{"error": "validation_error", "message": "unknown argument: min_kcal", "details": [{"type": "extra_forbidden", "loc": ["min_kcal"], "msg": "Extra inputs are not permitted"}]}
```

| `error` | When |
| --- | --- |
| `validation_error` | invalid or unknown arguments (`loc` names the field), unknown unit code, empty patch |
| `not_found` | unknown recipe id |
| `internal_error` | anything else; no internals in the result, details in the server log |

A missing or unknown key is answered before MCP with HTTP 401 and
`{"error": "unauthorized", ...}`.

### `list_units()`

The fixed unit vocabulary (adding one is a migration). `to_base` converts to
the dimension's base unit: grams, millilitres or items.

```json
{"items": [{"code": "can", "dimension": "count", "to_base": 1}, {"code": "g", "dimension": "mass", "to_base": 1}, ...]}
```

Codes: `g`, `kg`, `ml`, `l`, `tsp`, `tbsp`, `cup`, `piece`, `clove`, `can`,
`pinch`.

### `search_ingredients(q?, limit = 50, offset = 0)`

Ingredient names are normalized (trimmed, inner whitespace collapsed,
lowercased) and created the first time a recipe uses them. `q` is a
case-insensitive substring; results are in name order. `limit` is 1–200.

```json
// {"q": "chick"}
{"items": [{"id": 4, "name": "chickpea flour"}, {"id": 3, "name": "chickpeas"}], "limit": 50, "offset": 0}
```

### `create_recipe(recipe)`

```json
{"recipe": {
  "name": "Smoky hummus",
  "description": "Weeknight hummus.",
  "servings": 4,
  "prep_time_min": 10,
  "cook_time_min": 5,
  "steps": ["Blend everything.", "Season and serve."],
  "ingredients": [
    {"name": "Chickpeas", "quantity": 400, "unit": "g", "prep_note": "drained"},
    {"name": "tahini", "quantity": 2, "unit": "tbsp"},
    {"name": "salt"}
  ],
  "kcal": 1200, "protein_g": 48, "carbs_g": 120, "fat_g": 56
}}
```

Returns the stored recipe (as `get_recipe` does), with its new `id`. Rules:

- `name`, `servings` (> 0), at least one step, at least one ingredient line
  and all four macro totals (≥ 0, **for the whole recipe**) are required.
  Numbers are JSON numbers and are stored to one decimal place.
- An ingredient line has `name`, optional `quantity` (> 0) and `unit`
  (given together or not at all), optional `prep_note` and `optional`
  (default `false`).
- Unknown unit codes are rejected with `validation_error` naming the code.
- Derived fields (`*_per_serving`, `total_time_min`) and `id` are not
  accepted.

### `get_recipe(recipe_id)`

```json
{
  "kcal_per_serving": 300, "protein_per_serving": 12, "carbs_per_serving": 30, "fat_per_serving": 14,
  "id": 1, "name": "Smoky hummus", "servings": 4,
  "prep_time_min": 10, "cook_time_min": 5, "total_time_min": 15,
  "description": "Weeknight hummus.",
  "kcal": 1200, "protein_g": 48, "carbs_g": 120, "fat_g": 56,
  "steps": ["Blend everything.", "Season and serve."],
  "ingredients": [
    {"ingredient_id": 1, "name": "chickpeas", "quantity": 400, "unit": "g", "prep_note": "drained", "optional": false},
    ...
  ],
  "created_at": "2026-10-31T17:40:00.123456Z", "updated_at": "2026-10-31T17:40:00.123456Z"
}
```

Per-serving values are the totals divided by `servings`, rounded to one
decimal. `total_time_min` is prep + cook with a missing value counted as
zero, and null when both are missing.

### `update_recipe(recipe_id, changes)`

`changes` is a patch:

- Fields left out stay as they are.
- `steps` and `ingredients` replace the **whole** list, so send every step or
  line you want to keep.
- `null` clears `description`, `prep_time_min` or `cook_time_min`. Any other
  field can't be null.
- An empty patch is a `validation_error`.

```json
{"recipe_id": 1, "changes": {"servings": 6, "prep_time_min": null}}
```

The merged recipe is validated as a whole, with the same rules as
`create_recipe`. A failed update leaves the stored recipe unchanged. A
successful one returns the full stored recipe with a later `updated_at`.
Sending every field replaces the recipe.

### `delete_recipe(recipe_id)`

Deletes the recipe with its steps and ingredient lines. Ingredients stay in
the catalogue.

```json
{"id": 1, "deleted": true}
```

### `list_recipes(...)`

```json
// {"q": "hummus", "min_protein_per_serving": 10, "max_total_time": 30,
//  "all_ingredients": ["chickpeas"], "any_ingredients": ["tahini", "peanut_butter"],
//  "sort": "-protein_per_serving", "limit": 20}
{"items": [{"kcal_per_serving": 300, "protein_per_serving": 12, "carbs_per_serving": 30, "fat_per_serving": 14, "id": 1, "name": "Smoky hummus", "servings": 4, "prep_time_min": 10, "cook_time_min": 5, "total_time_min": 15}], "total": 1, "limit": 20, "offset": 0, "unmatched_ingredients": ["peanut_butter"]}
```

| Argument | Meaning |
| --- | --- |
| `q` | case-insensitive substring of the name |
| `max_total_time` | total time at most this many minutes (missing times count as zero) |
| `min_`/`max_` + `kcal_per_serving`, `protein_per_serving`, `carbs_per_serving`, `fat_per_serving` | inclusive per-serving bounds (kcal or grams per serving) |
| `all_ingredients` | ingredient names the recipe must all contain; normalized |
| `any_ingredients` | ingredient names of which the recipe must contain at least one; normalized |
| `sort` | `name` (default), `created_at`, `total_time`, or any `*_per_serving`; prefix `-` for descending |
| `limit`, `offset` | page size (default 50, 1–200) and offset |

Filters combine with AND, including the two ingredient lists. `total`
counts all matches, ignoring `limit` and `offset`. `unmatched_ingredients`
lists the requested names (normalized, in request order) that aren't in
the ingredient catalogue, so they can't match anything: here
`peanut_butter`. It is empty when every name is known.
Invalid values are a `validation_error`.
