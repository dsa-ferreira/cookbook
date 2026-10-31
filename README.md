# cookbook

A small recipe store with an HTTP API, meant to be driven by an AI assistant.
It keeps recipes with ordered steps, structured ingredient lines, timing and
whole-recipe macronutrients, and derives per-serving macros and total time.
Flask + SQLAlchemy on Postgres; every endpoint except `/healthz` needs an API
key.

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
`COOKBOOK_API_KEYS`. Clients send it as `Authorization: Bearer <key>`. The
request log records the key name, never the key.

## Running

### With docker compose

```sh
cp .env.example .env          # then put your entries in COOKBOOK_API_KEYS
docker compose up -d --build
curl http://localhost:8080/healthz
```

The `cookbook` container applies migrations (`cookbook migrate`) and then
starts gunicorn on port 8080. Data lives in the `pgdata` volume.

### Locally

```sh
export COOKBOOK_DATABASE_URL=postgresql://cookbook:cookbook@127.0.0.1:5432/cookbook
export COOKBOOK_API_KEYS='{"diogo": "<hash>"}'
make migrate
make run                      # gunicorn on 0.0.0.0:8080 (override with BIND=...)
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

## API

Every response is JSON. Errors look like this:

```json
{"error": "validation_error", "message": "request validation failed", "details": [{"loc": ["servings"], "msg": "Input should be greater than 0", "type": "greater_than"}]}
```

| Status | `error` | When |
| --- | --- | --- |
| 401 | `unauthorized` | missing, malformed or unknown key |
| 404 | `not_found` | unknown recipe id or route |
| 422 | `validation_error` | invalid body or query parameters, unknown unit code |
| 500 | `internal_error` | anything else (no internals in the response) |

The examples below assume:

```sh
export KEY=<your key>
export API=http://localhost:8080
```

### Health

```sh
curl $API/healthz
# {"status": "ok"}
```

### Units

The unit vocabulary is fixed (adding one is a migration). `to_base` converts
to the dimension's base unit: grams, millilitres or items.

```sh
curl -H "Authorization: Bearer $KEY" $API/units
# {"items": [{"code": "can", "dimension": "count", "to_base": 1}, ...]}
```

Codes: `g`, `kg`, `ml`, `l`, `tsp`, `tbsp`, `cup`, `piece`, `clove`, `can`,
`pinch`.

### Ingredients

Ingredient names are normalized (trimmed, inner whitespace collapsed,
lowercased) and created the first time a recipe uses them. Search before
writing a recipe to reuse existing names.

```sh
curl -H "Authorization: Bearer $KEY" "$API/ingredients?q=chick&limit=20&offset=0"
# {"items": [{"id": 3, "name": "chickpeas"}], "limit": 20, "offset": 0}
```

`q` is a case-insensitive substring. `limit` defaults to 50 (max 200).

### Create a recipe

```sh
curl -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -X POST $API/recipes -d '{
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
  }'
```

Returns 201 with the stored recipe and a `Location` header. Rules:

- `name`, `servings` (> 0), at least one step, at least one ingredient line
  and all four macro totals (≥ 0, for the whole recipe) are required.
- An ingredient line has `name`, optional `quantity` (> 0) and `unit`
  (given together or not at all), optional `prep_note` and `optional`
  (default `false`).
- Unknown unit codes are rejected with 422 naming the code.
- Derived fields (`*_per_serving`, `total_time_min`) and `id` are not
  accepted as input.

### Read a recipe

```sh
curl -H "Authorization: Bearer $KEY" $API/recipes/1
```

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

### Replace a recipe

`PUT` takes the same full document as `POST` and replaces everything,
including all steps and ingredient lines. There is no partial update.

```sh
curl -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -X PUT $API/recipes/1 -d '{
    "name": "Smoky hummus",
    "servings": 6,
    "steps": ["Blend everything."],
    "ingredients": [{"name": "chickpeas", "quantity": 800, "unit": "g"}],
    "kcal": 2000, "protein_g": 90, "carbs_g": 200, "fat_g": 80
  }'
```

A failed replace (422) leaves the stored recipe unchanged.

### Delete a recipe

```sh
curl -H "Authorization: Bearer $KEY" -X DELETE $API/recipes/1
# 204, no body
```

Ingredients stay in the catalogue.

### List and filter recipes

```sh
curl -H "Authorization: Bearer $KEY" \
  "$API/recipes?q=hummus&min_protein_per_serving=10&max_total_time=30&ingredient=chickpeas&ingredient=spinach&ingredient_match=any&sort=-protein_per_serving&limit=20"
```

```json
{"items": [{"kcal_per_serving": 300, "protein_per_serving": 12, "carbs_per_serving": 30, "fat_per_serving": 14, "id": 1, "name": "Smoky hummus", "servings": 4, "prep_time_min": 10, "cook_time_min": 5, "total_time_min": 15}], "total": 1, "limit": 20, "offset": 0}
```

| Parameter | Meaning |
| --- | --- |
| `q` | case-insensitive substring of the name |
| `max_total_time` | total time at most this many minutes (missing times count as zero) |
| `min_`/`max_` + `kcal_per_serving`, `protein_per_serving`, `carbs_per_serving`, `fat_per_serving` | inclusive per-serving bounds |
| `ingredient` | repeatable; names are normalized |
| `ingredient_match` | `all` (default: every listed ingredient) or `any` |
| `sort` | `name` (default), `created_at`, `total_time`, or any `*_per_serving`; prefix `-` for descending |
| `limit`, `offset` | page size (default 50, 1–200) and offset |

Filters combine with AND. `total` counts all matches, ignoring `limit` and
`offset`. Unknown parameters and invalid values return 422.
