# Proposal

## Why

We (two people) want a single place to store our recipes, so an AI assistant can help us decide what to eat and, later, build shopping lists. There's no app; the AI is the interface. So the first step is a small, well-structured recipe store behind an HTTP API. It records the steps, structured ingredients and macronutrients those later features depend on.

## What Changes

- New Python HTTP service (Flask) backed by Postgres, run locally with docker-compose and shipped as a container image.
- Recipes with name, description, servings, prep/cook time, ordered steps, structured ingredients, and macronutrient totals for the whole recipe. The service derives macros per serving.
- Ingredients are referenced by name and created on first use. Names are normalized so that "Chickpeas" and "chickpeas" are one ingredient. A search endpoint lets the AI reuse existing names.
- A curated, seeded set of units with a dimension (mass, volume or count) and a conversion factor to the base unit, so a shopping list can later sum quantities.
- Full CRUD on recipes, where update is a full-document replace (PUT). The recipe list can be filtered by name, total time, per-serving macro ranges and ingredients (all or any), and supports sorting and pagination.
- API-key authentication: one named key per person, configured as hashes in the service config. All endpoints except the health check require a key.

Out of scope (deferred): MCP server and skills, OpenAPI spec, PATCH, ingredient aliases/merging, volume-to-mass conversion, tags, per-person preferences, an "eaten" log, shopping lists, pantry ("only these ingredients") matching, user management and DB-backed keys.

## Capabilities

### New Capabilities
- `recipes`: storing, reading, replacing, deleting and listing/filtering recipes, including steps, ingredient lines, timing and macronutrients (totals and per serving).
- `ingredients`: the canonical ingredient catalogue: name normalization, get-or-create when recipes are written, and search.
- `units`: the curated unit vocabulary (dimension and conversion to base unit), and how unknown units are rejected.
- `api-auth`: API-key authentication for the HTTP API.

### Modified Capabilities

None. This is the first change in the project.

## Impact

- New codebase: Python 3.13 project managed with uv (Flask, SQLAlchemy 2.0, Alembic, psycopg 3, pydantic, pydantic-settings, gunicorn; dev: pytest, testcontainers, ruff).
- New Postgres database and Alembic migrations, including seed data for units.
- New HTTP API on the LAN; clients must send `Authorization: Bearer <key>`.
- New Makefile, Dockerfile and docker-compose.yml, following the conventions of the existing `mcparr` project.
