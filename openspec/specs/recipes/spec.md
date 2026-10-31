# recipes Specification

## Purpose

Stores our recipes (steps, structured ingredient lines, timing and macronutrients) and lets clients create, read, replace, delete and filter them, so an AI assistant can help decide what to eat.

## Requirements

### Requirement: Recipe document shape
A recipe SHALL consist of: a non-empty name, an optional description, a positive integer number of servings, optional prep and cook times in non-negative whole minutes, an ordered list of at least one non-empty step, an ordered list of at least one ingredient line, and whole-recipe macronutrient totals (kcal, protein, carbs, fat), each non-negative and required.

#### Scenario: Valid recipe is accepted
- **WHEN** a client creates a recipe with a name, 4 servings, one step, one ingredient line and all four macro totals
- **THEN** the recipe is stored and returned with status 201

#### Scenario: Missing macros are rejected
- **WHEN** a client creates a recipe without a protein total
- **THEN** the request is rejected with status 422 and an error that identifies the missing field

#### Scenario: Invalid servings are rejected
- **WHEN** a client creates a recipe with 0 servings
- **THEN** the request is rejected with status 422

#### Scenario: Recipe without steps is rejected
- **WHEN** a client creates a recipe with an empty step list
- **THEN** the request is rejected with status 422

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
- **THEN** the request is rejected with status 422

#### Scenario: Line order is preserved
- **WHEN** a recipe is created with ingredient lines in the order flour, butter, sugar
- **THEN** reading it returns the lines in the order flour, butter, sugar

### Requirement: Per-serving macronutrients
For every recipe the system SHALL expose per-serving kcal, protein, carbs and fat, equal to the corresponding total divided by servings and rounded to one decimal place. Per-serving values SHALL be derived only and never accepted as input.

#### Scenario: Per-serving values are derived
- **WHEN** a recipe has 3 servings and a protein total of 100 g
- **THEN** the recipe is returned with a protein-per-serving value of 33.3

#### Scenario: Changing servings updates per-serving values
- **WHEN** a recipe with 3 servings and 120 g protein total is replaced with 4 servings and the same totals
- **THEN** the recipe's protein per serving becomes 30.0

### Requirement: Total time
The system SHALL expose a total time equal to prep time plus cook time, treating a missing value as zero. Total time SHALL be null when both are missing.

#### Scenario: Total time from partial data
- **WHEN** a recipe has a cook time of 25 minutes and no prep time
- **THEN** its total time is 25

### Requirement: Create recipe
`POST /recipes` SHALL create a recipe from a full recipe document and return the stored recipe, including its id, derived values and timestamps, with status 201.

#### Scenario: Create returns the stored recipe
- **WHEN** a client posts a valid recipe document
- **THEN** the response has status 201 and contains the recipe with a server-assigned integer id

### Requirement: Read recipe
`GET /recipes/{id}` SHALL return the full recipe document. An unknown id SHALL return 404.

#### Scenario: Read existing recipe
- **WHEN** a client requests a recipe by an existing id
- **THEN** the full recipe including steps, ingredient lines, totals, per-serving macros and total time is returned with status 200

#### Scenario: Read unknown recipe
- **WHEN** a client requests a recipe id that does not exist
- **THEN** the response has status 404

### Requirement: Replace recipe
`PUT /recipes/{id}` SHALL replace the entire recipe with the submitted full document, including all steps and ingredient lines, atomically. Partial updates SHALL NOT be supported. An unknown id SHALL return 404.

#### Scenario: Replace swaps the ingredient list
- **WHEN** a recipe with ingredient lines A and B is replaced with a document containing only line C
- **THEN** reading the recipe returns only line C

#### Scenario: Failed replace leaves recipe unchanged
- **WHEN** a replace request fails validation, for example because it uses an unknown unit
- **THEN** the response has status 422 and the stored recipe is unchanged

### Requirement: Delete recipe
`DELETE /recipes/{id}` SHALL delete the recipe with its steps and ingredient lines and return 204. Ingredients in the catalogue SHALL NOT be deleted. An unknown id SHALL return 404.

#### Scenario: Delete keeps catalogue ingredients
- **WHEN** the only recipe using "tahini" is deleted
- **THEN** the recipe is gone and "tahini" is still returned by the ingredient search

### Requirement: List recipes
`GET /recipes` SHALL return a page of recipe summaries (id, name, servings, prep, cook and total time, per-serving macros) plus the total number of matching recipes. Pagination SHALL use `limit` (default 50, maximum 200) and `offset` (default 0).

#### Scenario: Default page
- **WHEN** a client lists recipes without parameters and 60 recipes exist
- **THEN** 50 summaries are returned and the total is 60

### Requirement: Filter recipes by name, time and macros
The list SHALL support these filters, combined with AND: `q` (case-insensitive substring of the name), `max_total_time`, and `min_`/`max_` bounds on `kcal_per_serving`, `protein_per_serving`, `carbs_per_serving` and `fat_per_serving` (inclusive). For the time filter, missing times SHALL count as zero.

#### Scenario: Combined filters
- **WHEN** a client lists with `min_protein_per_serving=30&max_total_time=30`
- **THEN** only recipes with at least 30 g protein per serving and a total time of at most 30 minutes are returned

#### Scenario: Name search is case-insensitive
- **WHEN** a client lists with `q=HUMMUS`
- **THEN** a recipe named "Smoky hummus" is returned

### Requirement: Filter recipes by ingredients
The list SHALL accept a repeated `ingredient` parameter matched against normalized ingredient names. With `ingredient_match=all` (default), only recipes containing every listed ingredient SHALL match. With `ingredient_match=any`, recipes containing at least one SHALL match.

#### Scenario: All ingredients required by default
- **WHEN** recipe R1 contains chickpeas and spinach, R2 contains only chickpeas, and a client lists with `ingredient=chickpeas&ingredient=spinach`
- **THEN** only R1 is returned

#### Scenario: Any ingredient
- **WHEN** the same recipes exist and a client lists with `ingredient=chickpeas&ingredient=spinach&ingredient_match=any`
- **THEN** both R1 and R2 are returned

#### Scenario: Ingredient names are normalized
- **WHEN** a client lists with `ingredient=%20Chickpeas`
- **THEN** recipes containing "chickpeas" are matched

### Requirement: Sort recipes
The list SHALL accept `sort` with one of `name`, `created_at`, `total_time`, `kcal_per_serving`, `protein_per_serving`, `carbs_per_serving`, `fat_per_serving`, optionally prefixed with `-` for descending order. The default SHALL be `name` ascending.

#### Scenario: Sort by protein descending
- **WHEN** a client lists with `sort=-protein_per_serving`
- **THEN** recipes are returned from highest to lowest protein per serving

### Requirement: Invalid list parameters are rejected
Unknown sort keys, non-numeric bounds, an `ingredient_match` other than `all` or `any`, and a `limit` outside 1 to 200 SHALL be rejected with status 422.

#### Scenario: Unknown sort key
- **WHEN** a client lists with `sort=tastiness`
- **THEN** the response has status 422
