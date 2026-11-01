# Spec Delta

## MODIFIED Requirements

### Requirement: Recipe document shape
A recipe SHALL consist of: a non-empty name, an optional description, a positive integer number of servings, optional prep and cook times in non-negative whole minutes, an ordered list of at least one non-empty step, an ordered list of at least one ingredient line, and whole-recipe macronutrient totals (kcal, protein, carbs, fat), each non-negative and required.

#### Scenario: Valid recipe is accepted
- **WHEN** a client calls `create_recipe` with a name, 4 servings, one step, one ingredient line and all four macro totals
- **THEN** the recipe is stored and returned

#### Scenario: Missing macros are rejected
- **WHEN** a client calls `create_recipe` without a protein total
- **THEN** the call returns a `validation_error` tool error that identifies the missing field

#### Scenario: Invalid servings are rejected
- **WHEN** a client calls `create_recipe` with 0 servings
- **THEN** the call returns a `validation_error` tool error

#### Scenario: Recipe without steps is rejected
- **WHEN** a client calls `create_recipe` with an empty step list
- **THEN** the call returns a `validation_error` tool error

### Requirement: Ingredient lines
Each ingredient line SHALL carry an ingredient name, an optional quantity (positive number), a unit code, an optional preparation note and an optional flag (default false). A unit SHALL be given if and only if a quantity is given. Order of lines SHALL be preserved, and the same ingredient MAY appear on more than one line.

#### Scenario: Quantity with unit
- **WHEN** a recipe includes the line `{name: "chickpeas", quantity: 400, unit: "g", prep_note: "drained"}`
- **THEN** reading the recipe returns that line with the same name, quantity, unit and preparation note

#### Scenario: Ingredient to taste
- **WHEN** a recipe includes the line `{name: "salt"}` with no quantity and no unit
- **THEN** the recipe is accepted and the line is returned with null quantity and unit

#### Scenario: Quantity without unit is rejected
- **WHEN** a recipe includes a line with quantity 2 and no unit
- **THEN** the call returns a `validation_error` tool error

#### Scenario: Line order is preserved
- **WHEN** a recipe is created with ingredient lines in the order flour, butter, sugar
- **THEN** reading it returns the lines in the order flour, butter, sugar

### Requirement: Per-serving macronutrients
For every recipe the system SHALL expose per-serving kcal, protein, carbs and fat, equal to the corresponding total divided by servings and rounded to one decimal place. Per-serving values SHALL be derived only and never accepted as input.

#### Scenario: Per-serving values are derived
- **WHEN** a recipe has 3 servings and a protein total of 100 g
- **THEN** the recipe is returned with a protein-per-serving value of 33.3

#### Scenario: Changing servings updates per-serving values
- **WHEN** a recipe with 3 servings and 120 g protein total is updated to 4 servings without changing its totals
- **THEN** the recipe's protein per serving becomes 30.0

#### Scenario: Per-serving values are not accepted as input
- **WHEN** a client calls `create_recipe` with a `protein_per_serving` field
- **THEN** the call returns a `validation_error` tool error

### Requirement: Create recipe
The `create_recipe` tool SHALL create a recipe from a full recipe document. It SHALL return the stored recipe, including its id, derived values and timestamps.

#### Scenario: Create returns the stored recipe
- **WHEN** a client calls `create_recipe` with a valid recipe document
- **THEN** the result contains the recipe with a server-assigned integer id

### Requirement: Read recipe
The `get_recipe` tool SHALL return the full recipe document for a recipe id. An unknown id SHALL return a `not_found` tool error.

#### Scenario: Read existing recipe
- **WHEN** a client calls `get_recipe` with an existing id
- **THEN** the full recipe is returned, including steps, ingredient lines, totals, per-serving macros and total time

#### Scenario: Read unknown recipe
- **WHEN** a client calls `get_recipe` with an id that does not exist
- **THEN** the call returns a `not_found` tool error

### Requirement: Delete recipe
The `delete_recipe` tool SHALL delete the recipe with its steps and ingredient lines, and confirm the deleted id. Ingredients in the catalogue SHALL NOT be deleted. An unknown id SHALL return a `not_found` tool error.

#### Scenario: Delete keeps catalogue ingredients
- **WHEN** the only recipe using "tahini" is deleted
- **THEN** the recipe is gone and "tahini" is still returned by `search_ingredients`

#### Scenario: Delete unknown recipe
- **WHEN** a client calls `delete_recipe` with an id that does not exist
- **THEN** the call returns a `not_found` tool error

### Requirement: List recipes
The `list_recipes` tool SHALL return a page of recipe summaries (id, name, servings, prep, cook and total time, per-serving macros) plus the total number of matching recipes. Pagination SHALL use `limit` (default 50, maximum 200) and `offset` (default 0).

#### Scenario: Default page
- **WHEN** a client calls `list_recipes` without arguments and 60 recipes exist
- **THEN** 50 summaries are returned and the total is 60

### Requirement: Filter recipes by name, time and macros
`list_recipes` SHALL support these filters, combined with AND: `q` (case-insensitive substring of the name), `max_total_time`, and `min_`/`max_` bounds on `kcal_per_serving`, `protein_per_serving`, `carbs_per_serving` and `fat_per_serving` (inclusive). For the time filter, missing times SHALL count as zero.

#### Scenario: Combined filters
- **WHEN** a client calls `list_recipes` with `min_protein_per_serving` 30 and `max_total_time` 30
- **THEN** only recipes with at least 30 g protein per serving and a total time of at most 30 minutes are returned

#### Scenario: Name search is case-insensitive
- **WHEN** a client calls `list_recipes` with `q` "HUMMUS"
- **THEN** a recipe named "Smoky hummus" is returned

### Requirement: Filter recipes by ingredients
`list_recipes` SHALL accept an `ingredients` list, matched against normalized ingredient names. With `ingredient_match` `all` (the default), only recipes containing every listed ingredient SHALL match. With `ingredient_match` `any`, recipes containing at least one SHALL match.

#### Scenario: All ingredients required by default
- **WHEN** recipe R1 contains chickpeas and spinach, R2 contains only chickpeas, and a client calls `list_recipes` with `ingredients` ["chickpeas", "spinach"]
- **THEN** only R1 is returned

#### Scenario: Any ingredient
- **WHEN** the same recipes exist and a client calls `list_recipes` with `ingredients` ["chickpeas", "spinach"] and `ingredient_match` "any"
- **THEN** both R1 and R2 are returned

#### Scenario: Ingredient names are normalized
- **WHEN** a client calls `list_recipes` with `ingredients` [" Chickpeas"]
- **THEN** recipes containing "chickpeas" are matched

### Requirement: Sort recipes
`list_recipes` SHALL accept `sort` with one of `name`, `created_at`, `total_time`, `kcal_per_serving`, `protein_per_serving`, `carbs_per_serving`, `fat_per_serving`, optionally prefixed with `-` for descending order. The default SHALL be `name` ascending.

#### Scenario: Sort by protein descending
- **WHEN** a client calls `list_recipes` with `sort` "-protein_per_serving"
- **THEN** recipes are returned from highest to lowest protein per serving

### Requirement: Invalid list parameters are rejected
`list_recipes` SHALL reject these with a `validation_error` tool error: unknown sort keys, non-numeric bounds, an `ingredient_match` other than `all` or `any`, and a `limit` outside 1 to 200.

#### Scenario: Unknown sort key
- **WHEN** a client calls `list_recipes` with `sort` "tastiness"
- **THEN** the call returns a `validation_error` tool error

## ADDED Requirements

### Requirement: Update recipe
The `update_recipe` tool SHALL take a recipe id and a patch of recipe document fields:
- Absent fields SHALL stay unchanged, and fields that are present SHALL be set.
- `steps` and `ingredients`, when present, SHALL replace the whole list.
- `null` SHALL clear `description`, `prep_time_min` or `cook_time_min`. On any other field, `null` SHALL be a validation error.
- An empty patch SHALL be a validation error.
- An unknown id SHALL return a `not_found` tool error.

#### Scenario: Patch one field
- **WHEN** a client calls `update_recipe` with only `name` "Weeknight dal" on a recipe with three steps
- **THEN** the name changes, and the steps, ingredient lines and totals are unchanged

#### Scenario: Patch replaces the ingredient list
- **WHEN** a recipe with ingredient lines A and B is updated with `ingredients` containing only line C
- **THEN** reading the recipe returns only line C

#### Scenario: Null clears an optional field
- **WHEN** a client calls `update_recipe` with `prep_time_min` null on a recipe with prep 10 and cook 20
- **THEN** prep time is null and total time is 20

#### Scenario: Null on a required field is rejected
- **WHEN** a client calls `update_recipe` with `servings` null
- **THEN** the call returns a `validation_error` tool error and the recipe is unchanged

#### Scenario: Empty patch is rejected
- **WHEN** a client calls `update_recipe` with no fields to change
- **THEN** the call returns a `validation_error` tool error

#### Scenario: Update unknown recipe
- **WHEN** a client calls `update_recipe` with an id that does not exist
- **THEN** the call returns a `not_found` tool error

### Requirement: Updates are validated as a whole and atomic
`update_recipe` SHALL merge the patch into the stored recipe and validate the result as a full recipe document, including rules that span fields and unit checks. If validation fails, the stored recipe SHALL be unchanged. A successful update SHALL return the full stored recipe and SHALL advance its update timestamp.

#### Scenario: Failed update leaves recipe unchanged
- **WHEN** an update fails validation, for example because a new ingredient line uses an unknown unit
- **THEN** the call returns a `validation_error` tool error and the stored recipe is unchanged

#### Scenario: Update returns the stored recipe
- **WHEN** a client successfully updates a recipe's steps
- **THEN** the result contains the full recipe with the new steps and a later `updated_at` than before

## REMOVED Requirements

### Requirement: Replace recipe
**Reason**: In a chat, a full-document replace makes the model re-send every step, line and total to change one field, which costs tokens and risks losing data.
**Migration**: Use `update_recipe`. Sending every document field in one patch does the same as the old replace.
