# Tasks

## 1. Project scaffolding

- [x] 1.1 Create the uv project (`pyproject.toml`, Python 3.13, `src/cookbook` package, uv_build backend) with dependencies flask, gunicorn, sqlalchemy, alembic, psycopg[binary], pydantic, pydantic-settings and dev group pytest, testcontainers[postgres], ruff, with the ruff config matching mcparr. Verify that `uv sync` succeeds and `uv run python -c "import cookbook"` works
- [x] 1.2 Add a Makefile with `install`, `lint`, `format`, `test`, `run`, `migrate`, `apikey`, `image` and `push` targets, following mcparr's conventions. Verify that `make lint` passes on the empty package
- [x] 1.3 Add `docker-compose.yml` with a `postgres:17` service (named volume, healthcheck) and verify that `docker compose up -d postgres` reports healthy

## 2. Configuration, database and test harness

- [x] 2.1 Implement `config.py` (pydantic-settings, `COOKBOOK_` prefix, `database_url`, `api_keys: dict[str, str]`). Startup validation rejects empty `api_keys` and values that aren't 64-character hex. Verify with unit tests for valid, empty and malformed key config
- [x] 2.2 Implement `db.py` (engine, sessionmaker, per-request session helper) and set up Alembic (`migrations/`, `env.py` reading the URL from settings). Verify that `uv run alembic upgrade head` runs against the compose Postgres with no revisions
- [x] 2.3 Add pytest fixtures: a session-scoped testcontainers Postgres with migrations applied, a per-test transaction rolled back afterwards, and a Flask test client with a known test key. Verify with a trivial test that connects and runs `SELECT 1`

## 3. Schema and units

- [x] 3.1 Define the ORM models for `units`, `ingredients`, `recipes` (with `Computed` per-serving and total-time columns), `recipe_steps` and `recipe_ingredients`, with all constraints from design.md. Generate and review the initial Alembic migration. Verify that `alembic upgrade head` and `alembic downgrade base` both succeed in a test
- [x] 3.2 Add a data migration that seeds the units from the units spec (g, kg, ml, l, tsp, tbsp, cup, piece, clove, can, pinch). Verify with a test that asserts the seeded codes, dimensions and factors
- [x] 3.3 Add DB-level tests for the constraints: generated per-serving values (100 g / 3 servings → 33.3), total time with null prep, quantity/unit both-or-neither CHECK, servings > 0, and the normalized-name CHECK on ingredients. Verify that the tests pass

## 4. App skeleton, errors and auth

- [x] 4.1 Implement `create_app()`, JSON error handlers (validation_error 422, not_found 404, unauthorized 401, internal_error 500), the `@validate_body` helper, and a `/healthz` blueprint. Verify with tests that a bad body returns the 422 JSON shape and an unknown route returns the 404 JSON shape
- [x] 4.2 Implement the `before_request` API-key check (Bearer parsing, SHA-256, `hmac.compare_digest`, exemption for `/healthz`, `g.api_key_name`) and request logging with the key name. Verify with tests for each api-auth scenario, including that a key is never logged
- [x] 4.3 Implement the `cookbook apikey NAME` CLI and the `make apikey` target. Verify with a test that the printed hash is the SHA-256 of the printed key and that the key authenticates when configured

## 5. Units and ingredients API

- [x] 5.1 Implement `normalize.py` (trim, collapse whitespace, lowercase). Verify with unit tests covering case, inner and outer whitespace, and blank input
- [x] 5.2 Implement `GET /units`. Verify with an API test that it returns all seeded units with dimension and factor
- [x] 5.3 Implement the ingredient service (get-or-create via `ON CONFLICT DO NOTHING`, search with `q`/limit/offset) and `GET /ingredients`. Verify with tests for each ingredients-spec scenario except the recipe-write ones (covered in 6.x)

## 6. Recipes write path

- [x] 6.1 Define the pydantic request/response schemas for the recipe document, including the line rule (quantity ⇔ unit), ≥1 step, ≥1 ingredient, non-negative macros and positive servings. Verify with unit tests for each validation scenario in the recipes spec
- [x] 6.2 Implement the recipe service create and `POST /recipes` (unit pre-check naming unknown codes, ingredient get-or-create, one transaction). Verify with API tests for create, the unknown unit 422, the rejected recipe creating no ingredients, and ingredient reuse across case variants
- [x] 6.3 Implement `GET /recipes/{id}` (full document with per-serving values and total time, lines and steps in order) and `DELETE /recipes/{id}`. Verify with tests for read, 404, ordering, and the catalogue ingredient surviving a delete
- [x] 6.4 Implement `PUT /recipes/{id}` as an atomic full replace. Verify with tests that the ingredient list is swapped, servings change updates per-serving values, a failed replace leaves the recipe unchanged, and an unknown id gives 404

## 7. Recipes list and filtering

- [x] 7.1 Implement the `RecipeListParams` model (q, max_total_time, min/max per-serving bounds, repeated `ingredient`, `ingredient_match`, `sort`, `limit` 1–200, `offset`) with 422s on invalid values. Verify with tests for an unknown sort key, a bad ingredient_match and an out-of-range limit
- [x] 7.2 Implement `GET /recipes` with summaries, total count, pagination, name/time/macro filters and sorting. Verify with tests for the default page (60 recipes → 50 + total 60), the combined filters, case-insensitive `q`, and `-protein_per_serving` ordering
- [x] 7.3 Implement the ingredient filter (all by default, any switch, normalized names). Verify with tests for the R1/R2 all and any scenarios and the normalized-name scenario

## 8. Packaging and integration

- [x] 8.1 Add the multi-stage Dockerfile (uv builder, non-root runtime, HEALTHCHECK on `/healthz`, entrypoint running `cookbook migrate` and then gunicorn) and add the `cookbook` service to docker-compose. Verify that `docker compose up` starts both services and `/healthz` returns 200
- [x] 8.2 Write a README covering setup, configuration (`COOKBOOK_DATABASE_URL`, `COOKBOOK_API_KEYS`), key generation, running and testing, plus a curl example per endpoint. Verify by following it from a clean checkout: create a recipe, filter it, replace it and delete it with curl using a generated key
- [x] 8.3 Run `make lint` and `make test` on the full suite and verify both pass

## Workflow follow-up

- Archive the change with `/opsx:archive` once implemented and reviewed, then verify the main specs were created under `openspec/specs/`.
