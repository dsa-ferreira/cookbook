# Tasks

## 1. Reject unknown arguments on every tool

- [x] 1.1 In `common/mcp/server.py`, make `CookbookServer` set `additionalProperties: false` on each registered tool's input schema. Verify with a `tests/test_catalogue.py` test that every tool in `tools/list` has the flag.
- [x] 1.2 In `CookbookServer.call_tool`, return a `validation_error` with one `extra_forbidden` details entry per undeclared argument, before the tool runs. Verify with tests in `tests/common/test_mcp_errors.py`: `list_recipes` with `min_kcal`, and `get_recipe` with two extra keys, both named.
- [x] 1.3 Update the README's Errors section to say that unknown arguments are rejected. Check that the example body matches a real error.

## 2. Log rejected calls

- [x] 2.1 In `CookbookServer.call_tool`, log every `validation_error` result at WARNING on `cookbook.mcp`, with the tool name, the sorted argument keys and the details. Verify with `caplog` tests: the argument-stage error (dict `all_ingredients`), the unknown-argument error, and an in-tool error (unknown unit code) are all logged.
- [x] 2.2 Add a test that a `create_recipe` call with `servings` 0 logs `recipe.servings` and none of the recipe's values (name, steps).

## 3. Rework `list_recipes` arguments

- [x] 3.1 In `recipes/schemas.py`, add a `SortKey` `Literal` with the 14 values, derive `SORT_KEYS` from it, and drop the `_sort_key` validator. Replace `ingredients`/`ingredient_match` in `RecipeListParams` with `all_ingredients`/`any_ingredients`, keeping normalization, de-duplication and the blank-name check. Update `tests/recipes/test_list_params.py`.
- [x] 3.2 In `recipes/service.py`, apply the "all" and "any" filters independently and combine them with AND. Verify with service or tool tests covering the four ingredient scenarios in the recipes spec delta (all, any, both, normalized).
- [x] 3.3 Add `unmatched_ingredients: list[str]` (described) to `RecipeList`, filled from one catalogue lookup over both lists, in request order. Verify with tests for `["chicken", "peanut_butter"]` (empty result, `["peanut_butter"]` reported) and for a known name (empty list).
- [x] 3.4 Update the `list_recipes` tool signature in `recipes/tools.py` to the new arguments and the `SortKey` type, and trim the docstring to what the tool does. Verify in `tests/recipes/test_tools_list.py`: `sort` "tastiness" and `all_ingredients` as an object return `validation_error`, and `ingredients`/`ingredient_match` are rejected as unknown.
- [x] 3.5 Update the README's `list_recipes` example, argument table and result fields. Check that the example call succeeds against the test server, or matches a test.

## 4. Describe every tool argument

- [x] 4.1 Add `Field(description=...)` to every `list_recipes` argument, with the text kept in `recipes/schemas.py`. Give the unit (minutes, grams or kcal per serving), say that bounds are inclusive, and give an example for each ingredient list (e.g. `["chicken", "peanut butter"]`, names as in `search_ingredients`).
- [x] 4.2 Describe the remaining arguments: `Limit` and `Offset` in `common/fields.py`, `q` in `search_ingredients`, `recipe_id` in `get_recipe`/`update_recipe`/`delete_recipe`, `recipe` in `create_recipe`, and `changes` in `update_recipe`.
- [x] 4.3 Replace `test_every_recipe_field_is_described` with a test over every tool: every top-level and every `$defs` property has a non-empty description. Add a test that the `sort` enum has exactly the 14 values, and that `min_protein_per_serving` mentions grams per serving. Update `test_decimal_inputs_are_numbers` if the bound schema shape changed.

## 5. Integration check

- [x] 5.1 Run `make lint` and `make test`. Both pass.
- [x] 5.2 Dump `tools/list` for `list_recipes` and review it as a model would see it. Check that there are no title-only properties, that `sort` is an enum, that `additionalProperties` is false, and that the ingredient lists have examples.

## Workflow follow-up

- Bump the version (breaking tool interface change) and write the handover update for the release.
- Update agent prompts or clients that use `ingredients`, `ingredient_match` or extra arguments.
- Archive the change after review.
