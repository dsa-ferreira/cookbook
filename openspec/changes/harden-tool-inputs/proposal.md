# Proposal

## Why

Agents call `list_recipes` with malformed arguments, for example
`{"ingredients": {"chicken": "all", "peanut_butter": "all"}}`. The tool
schemas invite these mistakes. Argument names that the server does not know
are silently dropped. `ingredients` and `ingredient_match` only make sense
together, but they are linked only in the docstring. `sort` is a free
string. Ingredient names that match nothing give an empty result with no
hint why. No tool argument has a description of its own. The server also
does not log rejected calls, so we can't see how often agents get a call
wrong or whether a fix helped.

## What Changes

- Every tool rejects arguments it does not declare with a
  `validation_error` that names each one. Input schemas declare
  `additionalProperties: false`. **BREAKING** for clients that send extra
  arguments: their calls fail instead of being silently ignored.
- `list_recipes` replaces `ingredients` + `ingredient_match` with two
  independent lists. `all_ingredients`: the recipe contains every name.
  `any_ingredients`: the recipe contains at least one. A call can use both,
  and they combine with AND. **BREAKING**: the old argument names are
  rejected as unknown.
- `list_recipes` declares `sort` as an enum of its 14 valid values, so
  clients see them in the schema.
- Every argument of every tool has a description. Where it matters, the
  description gives the unit (minutes, grams or kcal per serving), says
  whether the value is per serving, and shows an example value. A
  catalogue test enforces this for all tools.
- `list_recipes` results include `unmatched_ingredients`: requested names
  that are not in the ingredient catalogue. This explains an empty or
  short result such as one caused by `"peanut_butter"`.
- Every call rejected with `validation_error` is logged at WARNING with
  the tool name, the argument names sent, and the error details. Argument
  values are not logged.

Out of scope: the output schema advertising per-serving macros as
`number | string`, and treating `_` as a space in ingredient names.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mcp-server`: unknown tool arguments are rejected, every tool argument
  is described in the input schema, and rejected calls are logged.
- `recipes`: `list_recipes` ingredient filtering moves to `all_ingredients`
  and `any_ingredients`, `sort` is an enum in the schema, and results
  report unmatched ingredient names.

## Impact

- Code: `common/mcp/server.py` (unknown-argument check, schema flag,
  logging), `recipes/schemas.py` and `recipes/tools.py` (list arguments,
  descriptions, sort enum, `RecipeList.unmatched_ingredients`),
  `recipes/service.py` (ingredient filters, unmatched lookup), and
  `units/tools.py` and `ingredients/tools.py` (argument descriptions).
- Tests: `tests/test_catalogue.py`, `tests/recipes/test_list_params.py`,
  `tests/recipes/test_tools_list.py`, and new tests for unknown arguments
  and logging.
- Docs: the README's `list_recipes` section and its error description.
- Clients: any agent prompt or client that uses `ingredients`,
  `ingredient_match` or extra arguments has to change. This is a breaking
  change to the tool interface, so the release needs a version bump and a
  handover update.
