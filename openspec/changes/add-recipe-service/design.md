# Design

## Context

This is a greenfield repository with no existing code. See proposal.md for the motivation and scope; the behavior contract lives in `specs/` (recipes, ingredients, units, api-auth). The service runs on the home LAN for two users, and its only client is an AI assistant, at first through raw HTTP and later through an MCP layer. Tooling follows the existing `mcparr` project: uv, Python 3.13, ruff, pytest, pydantic-settings, a Makefile, a multi-stage Dockerfile and the `album.lan` registry.

## Goals / Non-Goals

**Goals:**
- A schema that is the long-lived asset. Constraints live in Postgres, not only in Python.
- A data layer that is independent of the web framework, so a later MCP server or CLI can reuse it.
- Small, explicit glue code that the owner can read in full. No framework magic is needed to understand it.

**Non-Goals:**
- Async I/O, horizontal scaling and caching. The service has two users.
- OpenAPI generation. It can be added later with flask-openapi3 or similar if needed.
- Volume-to-mass conversion (that would need per-ingredient densities).

## Decisions

### Stack
- **Flask (sync) + gunicorn.** The owner already knows Flask, and the sync model fits the load. Alternative: FastAPI, which gives pydantic validation and OpenAPI for free. It was rejected because familiarity matters more here, and the glue it would replace is about 30 lines.
- **pydantic by hand for request/response models.** A small `@validate_body(Model)` decorator parses `request.get_json()` into the model and passes it to the view. One error handler turns `pydantic.ValidationError` into 422 `{"error": "validation_error", "details": [...]}`. Query parameters for the list endpoint are parsed the same way, into a `RecipeListParams` model. Alternatives: flask-openapi3 (deferred until there is a need for OpenAPI), and marshmallow-based APIFlask or flask-smorest (rejected because they would add a second validation library).
- **SQLAlchemy 2.0 typed ORM, plain rather than Flask-SQLAlchemy.** A module-level `engine` and `sessionmaker`. Each request gets one session (opened lazily on `flask.g`, committed by the view's service call, closed in `teardown_appcontext`). Alternative: Flask-SQLAlchemy, rejected because it ties models and sessions to the app context, which complicates Alembic, tests and future non-Flask consumers. Raw psycopg was also considered and rejected: the unit of work makes it simple to write one recipe across four tables in a single transaction.
- **Alembic** with autogenerate, used as a starting point and reviewed by hand. **psycopg 3** as the driver.
- **pydantic-settings** for config, with the `COOKBOOK_` env prefix: `COOKBOOK_DATABASE_URL`, `COOKBOOK_API_KEYS`.

### Project layout
The code is organized by domain, not by layer. Each domain package owns its tables, schemas, logic and HTTP routes, so a new domain is a new package rather than an edit to every layer, and no single models or schemas file grows with the project. Framework and infrastructure code that every domain uses lives under `common/`, so the top level holds only domains and entry points.
```
src/cookbook/
  units/           models, schemas, service, api
  ingredients/     models, schemas, service, api, normalize
  recipes/         models, schemas, service (write/read), listing (filters), api
  common/          shared infrastructure, no domain logic
    config.py      settings
    db.py          declarative Base + naming convention, engine, sessionmaker
    migrate.py     run Alembic from code
    auth.py        before_request key check, access log
    errors.py      domain errors (not found, invalid input)
    fields.py      pydantic field types shared by the domain schemas
    web/           Flask glue: JSON errors, @validate_body / query parsing,
                   per-request session, /healthz
  app.py           entry point: create_app() wires common/ and each domain's blueprint
  cli.py           entry point: `cookbook apikey`, `cookbook migrate`
migrations/        alembic env (imports every domain's models) + versions (incl. units seed)
tests/             mirrors the source (tests/common/, tests/recipes/, ...)
```
Dependencies point one way: domains depend on `common/`, never the reverse, and recipes → ingredients and units; neither depends on recipes. The services, models and schemas take a `Session` and pydantic models and return pydantic models. They don't import Flask; only the domains' `api.py` modules and `common/web/` do. This is what makes a later MCP layer cheap to add.

### Schema
```
units(code text PK, dimension text CHECK IN (mass,volume,count), to_base numeric NOT NULL > 0)
ingredients(id bigint identity PK, name text UNIQUE NOT NULL CHECK (name <> ''))
recipes(id bigint identity PK, name text NOT NULL, description text,
        servings int NOT NULL CHECK > 0,
        prep_time_min int CHECK >= 0, cook_time_min int CHECK >= 0,
        kcal, protein_g, carbs_g, fat_g numeric(7,1) NOT NULL CHECK >= 0,
        {kcal,protein_g,carbs_g,fat_g}_per_serving numeric
            GENERATED ALWAYS AS (round(x / servings, 1)) STORED,
        total_time_min int GENERATED ALWAYS AS (...) STORED,
        created_at, updated_at timestamptz NOT NULL)
recipe_steps(recipe_id FK ON DELETE CASCADE, position int, text text NOT NULL,
             PK(recipe_id, position))
recipe_ingredients(id bigint identity PK, recipe_id FK ON DELETE CASCADE,
                   ingredient_id FK, position int, quantity numeric NULL CHECK > 0,
                   unit text NULL FK units, prep_note text, optional bool NOT NULL default false,
                   UNIQUE(recipe_id, position),
                   CHECK ((quantity IS NULL) = (unit IS NULL)))
```
- **ids are bigint identity, not UUIDs.** There is one database and no client-generated ids. Small integers are also easier for an AI to quote back accurately.
- **Macro totals are the source of truth; per-serving values are stored generated columns.** Totals match how macros are produced (summed over the whole pot), and changing `servings` never requires rescaling. Generated columns keep the derivation in the database, can't drift, and turn per-serving filters into plain column comparisons. Alternatives were a view (one more mapped object) and a SQLAlchemy `hybrid_property` (logic only in the app). Mapped with `Computed(...)` so that Alembic and the ORM treat the columns as read-only. `total_time_min` follows the same pattern, so that sorting and filtering by total time is a plain column comparison.
- **Ingredient names are stored already normalized** (the app normalizes them). A plain UNIQUE constraint therefore enforces case-insensitive identity, and no citext extension is needed. A CHECK `name = lower(name)` guards against writes that bypass normalization.
- **Units are a lookup table** seeded by an Alembic data migration. Adding a unit is an insert in a new migration, not an enum ALTER. The ingredient line's FK on `unit` produces the "unknown unit" rejection. The service also pre-checks codes so that the 422 can name the unknown one rather than surfacing an IntegrityError.
- **Steps are rows rather than `text[]`.** They follow the same ordered-child pattern as ingredient lines and leave room for per-step data such as durations.

### Writes
- **Create/replace is one transaction.** Validate units, get-or-create ingredients, then upsert the recipe row. On replace, the existing steps and ingredient lines are deleted and the submitted ones inserted. Any failure rolls back the whole transaction, including newly created ingredients (see the ingredients spec).
- **Get-or-create** uses `INSERT ... ON CONFLICT (name) DO NOTHING` followed by `SELECT`, which is race-free without application locking.
- **No PATCH.** Merge semantics on nested lists are ambiguous. An AI client can cheaply send the full document.

### Listing
- Filters are built as a single SQLAlchemy `select` over `recipes` with optional `WHERE` clauses on the generated columns.
- The ingredient filter normalizes the given names, then:
  - all: `recipes.id IN (SELECT recipe_id FROM recipe_ingredients JOIN ingredients ... WHERE name IN (:names) GROUP BY recipe_id HAVING count(DISTINCT ingredient_id) = :n)`, where `n` is the number of distinct normalized names.
  - any: `EXISTS` with `name IN (:names)`.
- `total` comes from a `count(*)` over the same filtered query, without limit or offset.

### Auth
- **Keys live in config, not the DB.** `COOKBOOK_API_KEYS` is a JSON object `{"name": "<sha256 hex>"}`. Rotating a key means editing env and restarting, which is fine for two rarely-changing keys. Alternative: an `api_keys` table, rejected because it would need a management path and edge towards user management.
- **Plain SHA-256, not bcrypt or argon2.** The keys are 32-byte random tokens, not human-chosen passwords, so slow hashing adds no security.
- A `before_request` hook skips `/healthz`, parses `Authorization: Bearer`, hashes the token and compares it against each configured hash with `hmac.compare_digest`. On a match it stores the key name on `g.api_key_name`, which a log filter adds to request log lines.
- **The service refuses to start with zero configured keys**, so a misconfigured deploy can't come up open.
- `cookbook apikey NAME`, wrapped by `make apikey NAME=x`, prints a fresh `secrets.token_urlsafe(32)` key once, along with the `"NAME": "<hash>"` entry to paste into config.

### Errors
All errors are JSON: `{"error": "<code>", "message": "...", "details"?: [...]}`. The codes are `validation_error` (422), `not_found` (404), `unauthorized` (401) and `internal_error` (500, with no internals leaked).

### Runtime & tests
- **docker-compose** runs `postgres:17` with a volume and `cookbook`. The `cookbook` container runs `cookbook migrate` (`alembic upgrade head`) and then starts gunicorn. For a single-instance service, migrating on start is simpler than a separate job.
- **Tests** use pytest with a session-scoped testcontainers Postgres and Alembic migrations applied once. Each test runs inside a transaction that is rolled back afterwards. API tests go through Flask's test client with a test key configured. There is no SQLite stand-in, because the generated columns and constraints must run against real Postgres.

## Risks / Trade-offs

- [Synonyms/plurals ("chickpea" vs "chickpeas") still create duplicates] → The AI is expected to call `GET /ingredients?q=` before writing. A future change can add aliases or a merge operation.
- [Migrating on container start could hit a bad migration in prod] → Single instance, `pg_dump` before deploying changes that include migrations, and Alembic downgrade scripts are kept.
- [Full-replace PUT allows lost updates if both users edit the same recipe at once] → This is unlikely with two users. `updated_at` could later back an `If-Match`-style check.
- [Rounding to one decimal on per-serving values] → Totals stay exact, and only derived values are rounded.
- [Count-dimension units (can, clove) can't be converted between each other] → This is by design. A shopping list will sum them per unit.

## Migration Plan

This is the first deploy, with nothing to migrate from. Build the image, push it to `album.lan`, start with compose (migrations run automatically), generate two keys with `make apikey` and set `COOKBOOK_API_KEYS`. To roll back, stop the container. The database volume is unaffected by the image version.
