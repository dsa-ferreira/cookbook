# Spec Delta

## Purpose

Exposes the cookbook to AI assistants as an MCP server over Streamable HTTP. It is the only interface to recipe, ingredient and unit data.

## ADDED Requirements

### Requirement: Streamable HTTP endpoint
The service SHALL serve the Model Context Protocol over Streamable HTTP at the path `/mcp`. The endpoint SHALL be stateless: each request stands alone, without a server-side MCP session. It SHALL answer with JSON responses rather than event streams.

#### Scenario: Client initializes and lists tools
- **WHEN** an MCP client with a valid key sends `initialize` and then `tools/list` to `/mcp`
- **THEN** both requests succeed with JSON responses, and the tool list is returned

#### Scenario: No session required between calls
- **WHEN** a client sends a `tools/call` request without a session id from an earlier request
- **THEN** the call is processed normally

### Requirement: Tool catalogue
The server SHALL expose exactly these tools: `list_units`, `search_ingredients`, `list_recipes`, `get_recipe`, `create_recipe`, `update_recipe` and `delete_recipe`. It SHALL NOT expose MCP resources or prompts.

#### Scenario: Seven tools are listed
- **WHEN** a client calls `tools/list`
- **THEN** exactly the seven named tools are returned, each with a description and an input schema

### Requirement: Tool annotations
Each tool SHALL carry MCP annotations describing its effect:
- `list_units`, `search_ingredients`, `list_recipes` and `get_recipe` SHALL be marked read-only.
- `update_recipe` SHALL be marked idempotent and not destructive.
- `delete_recipe` SHALL be marked destructive and idempotent.
- `create_recipe` SHALL be marked neither read-only nor idempotent.

#### Scenario: Delete is flagged as destructive
- **WHEN** a client calls `tools/list`
- **THEN** `delete_recipe` has `destructiveHint` true and `get_recipe` has `readOnlyHint` true

### Requirement: Numeric inputs are JSON numbers
Tool input schemas SHALL describe quantities, macronutrient totals and macronutrient bounds as JSON numbers, not as strings. Numbers SHALL be stored without binary floating-point error, within the precision the recipe document allows.

#### Scenario: Decimal macro accepted as a number
- **WHEN** a client creates a recipe with `protein_g` set to the JSON number `12.3`
- **THEN** reading the recipe returns `protein_g` as `12.3`

### Requirement: Structured tool results
Every successful tool call SHALL return structured content that matches the tool's declared output schema. The same data SHALL also be returned as JSON text content, for clients that ignore structured content.

#### Scenario: Get recipe returns structured content
- **WHEN** a client calls `get_recipe` for an existing recipe
- **THEN** the result has `isError` false, and its structured content contains the recipe's id, name, steps and ingredient lines

### Requirement: Tool error results
A failed tool call SHALL return a result with `isError` true, not a protocol error. Its content SHALL include an error code and a human-readable message:
- `validation_error`: the message or details SHALL identify each offending field.
- `not_found`: an unknown recipe id.
- `internal_error`: the result SHALL NOT expose internal details.

#### Scenario: Validation error names the field
- **WHEN** a client calls `create_recipe` with `servings` set to 0
- **THEN** the result has `isError` true, code `validation_error`, and identifies `servings`

#### Scenario: Unknown recipe
- **WHEN** a client calls `get_recipe` with an id that does not exist
- **THEN** the result has `isError` true and code `not_found`

#### Scenario: Unexpected failure hides internals
- **WHEN** a tool fails because of an unexpected server error
- **THEN** the result has `isError` true and code `internal_error`, and its content contains no stack trace, SQL or connection details

### Requirement: Server instructions
The server SHALL provide MCP server instructions that tell clients to search the ingredient catalogue before writing recipes, so they reuse existing names. The instructions SHALL also say that units come from a fixed vocabulary listed by `list_units`, and that macronutrients are whole-recipe totals.

#### Scenario: Instructions returned on initialize
- **WHEN** a client sends `initialize`
- **THEN** the response includes instructions that mention `search_ingredients`, `list_units` and whole-recipe macro totals

### Requirement: No REST data endpoints
The service SHALL NOT serve recipe, ingredient or unit data on any path other than `/mcp`. The former REST paths SHALL respond with 404 to authenticated requests.

#### Scenario: Former REST path is gone
- **WHEN** a client calls `GET /recipes` with a valid key
- **THEN** the response has status 404
