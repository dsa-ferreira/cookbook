# Design

## Context

See proposal.md for the problem. These facts about the current code shape
the approach:

- The MCP SDK builds each tool's arguments model from the function
  signature. That model uses Pydantic's default `extra="ignore"`, so
  undeclared top-level arguments are dropped before the tool runs. The
  nested input models (`RecipeIn`, `RecipePatch`, `IngredientLineIn`,
  `RecipeListParams`) already set `extra="forbid"`, so only the top level
  needs fixing.
- `CookbookServer.call_tool` (`common/mcp/server.py`) already wraps the
  SDK. It turns argument `ValidationError`s into the
  `{"error", "message", "details"}` body. Errors raised inside a tool body
  go through `tool_errors` instead. Both paths end in `to_error_result`,
  but only `call_tool` knows the tool name and the raw arguments.
- `list_recipes` takes flat arguments and copies them into
  `RecipeListParams`, which does the validation (normalization, sort key
  check). The service filters by exact normalized name.

## Goals / Non-Goals

**Goals:**
- One place that enforces "no unknown arguments" for every tool, present
  and future, with a schema that says so.
- Arguments that the schema alone describes correctly, without depending
  on the docstring.
- Enough logging to count and classify bad calls after the release.

**Non-Goals:**
- Accepting or converting malformed shapes (for example a name-to-mode
  dict). Rejecting them clearly is the fix.
- Fuzzy matching of ingredient names. Reporting unmatched names is enough
  for now.
- Changing `list_recipes` to take a single nested `params` object.

## Decisions

### Unknown arguments: check in `CookbookServer`, not per tool

`CookbookServer` looks up the tool and compares the argument keys with
the properties in its input schema. If any key is undeclared, it returns
a `validation_error` without calling the SDK. There is one details entry
per undeclared key, shaped like Pydantic's `extra_forbidden` error
(`loc: [name]`, `type: "extra_forbidden"`, `msg: "Extra inputs are not
permitted"`). The details then look the same as a nested-model error.
When a tool is registered, `CookbookServer` also sets
`additionalProperties: false` on its input schema, so the advertised
schema and the check use the same property list.

*Alternatives:* set `extra="forbid"` on each SDK arguments model. That
relies on SDK internals (`fn_metadata.arg_model`) and would have to be
rebuilt after the SDK creates it. Another option is a `**kwargs` catch in
each tool, but every tool would have to remember to add it.

### Ingredient filters: two independent lists, not a list plus a mode

`all_ingredients: list[str] | None` and `any_ingredients: list[str] |
None` replace `ingredients` and `ingredient_match`. Each list keeps the
current normalization and de-duplication, and still rejects blank names.
The service applies the existing "all" and "any" subqueries, one per
non-empty list, combined with AND.

*Why:* the reported failure comes from the model merging two linked
arguments into one. With no mode value left, a name-to-mode mapping has
nothing to map to. *Alternatives:* keep the pair and only add
descriptions. That is cheaper but leaves the coupling in place. Accepting
a dict was rejected; see Non-Goals.

### `sort` as a `Literal` enum

Define a `SortKey` `Literal` with all 14 values in `recipes/schemas.py`
and use it as the argument type. Pydantic then emits an `enum` and checks
the value. Derive `SORT_KEYS` from it (the unprefixed values) so the
service's ordering map still has one source. The custom `_sort_key`
validator goes away. Pydantic's `literal_error` names the allowed values.

### Descriptions live with the schemas

The `list_recipes` arguments stay flat in the tool signature, each typed
`Annotated[<type>, Field(description=...)]`. The description text lives
in `recipes/schemas.py` next to `_DOC`, so `RecipeListParams` and the
signature use the same strings. The other tools' arguments (`q`, `limit`,
`offset`, `recipe_id`, `recipe`, `changes`) get descriptions the same way.
The shared `Limit` and `Offset` types in `common/fields.py` get a generic
description, so each tool doesn't repeat it. The tool docstring shrinks
to what the tool does. Per-argument rules move to the arguments.

The catalogue test checks every property of every tool's input schema,
including nested `$defs`. That replaces the recipe-only test.

### `unmatched_ingredients` from one catalogue query

After building the filtered query, the service collects the names from
both lists and selects which of them exist in `ingredients.name`. It
returns the missing ones in request order. This is one extra query, and
it runs only when an ingredient filter is given. The field is always
present in `RecipeList`, as an empty list when nothing is missing, so
clients don't need a null check.

### Logging in `CookbookServer.call_tool`

After the call, if the result is an error with code `validation_error`,
log at WARNING on the `cookbook.mcp` logger:
`tool %s rejected: args=%s details=%s`, with the tool name, the sorted
argument keys and the details list. The details are already built with
`include_input=False`, so they contain no values. Errors from inside a
tool body (for example an unknown unit code) reach this point as returned
results, so one place covers both paths.

*Alternative:* log in `to_error_result`. It doesn't know the tool name or
the argument keys.

## Risks / Trade-offs

- [Breaking change for existing agents and prompts that send `ingredients`
  or extra arguments] → The error names the unknown argument, and the
  schema shows the new ones, so agents usually recover on the next call.
  Bump the minor version and note it in the handover update.
- [Some MCP clients add their own fields to `arguments`] → No such client
  is known. If one turns up, add an allow-list in `CookbookServer` rather
  than relaxing the check.
- [Custom validator messages could echo input values into the log] →
  Current custom messages (`must not be blank`, `ingredient names must not
  be blank`) don't contain values. Keep it that way, and test it with the
  `create_recipe` logging scenario.
- [Longer schemas cost tokens on every `tools/list`] → Keep each
  description to one or two sentences.

## Migration Plan

Deploy as a normal release (version bump plus handover update). There is
no data migration. To roll back, deploy the previous image. Clients
updated for the new argument names would then hit the old server's
silent-drop behavior, so roll back the agent prompts too.
