# Spec Delta

## MODIFIED Requirements

### Requirement: Filter recipes by ingredients
`list_recipes` SHALL accept two lists of ingredient names, matched against normalized ingredient names. With `all_ingredients`, only recipes containing every listed ingredient SHALL match. With `any_ingredients`, only recipes containing at least one listed ingredient SHALL match. When both are given, a recipe SHALL satisfy both. An empty or omitted list SHALL NOT filter.

#### Scenario: All ingredients required by default
- **WHEN** recipe R1 contains chickpeas and spinach, R2 contains only chickpeas, and a client calls `list_recipes` with `all_ingredients` ["chickpeas", "spinach"]
- **THEN** only R1 is returned

#### Scenario: Any ingredient
- **WHEN** the same recipes exist and a client calls `list_recipes` with `any_ingredients` ["chickpeas", "spinach"]
- **THEN** both R1 and R2 are returned

#### Scenario: Both lists combine with AND
- **WHEN** R1 contains chickpeas and lemon, R2 contains chickpeas and lime, R3 contains only lemon, and a client calls `list_recipes` with `all_ingredients` ["chickpeas"] and `any_ingredients` ["lemon", "lime"]
- **THEN** R1 and R2 are returned, and R3 is not

#### Scenario: Ingredient names are normalized
- **WHEN** a client calls `list_recipes` with `all_ingredients` [" Chickpeas"]
- **THEN** recipes containing "chickpeas" are matched

#### Scenario: Former ingredient arguments are rejected
- **WHEN** a client calls `list_recipes` with `ingredients` ["chickpeas"] or with `ingredient_match` "any"
- **THEN** the call returns a `validation_error` tool error that identifies the unknown argument

### Requirement: Sort recipes
`list_recipes` SHALL accept `sort` with one of `name`, `created_at`, `total_time`, `kcal_per_serving`, `protein_per_serving`, `carbs_per_serving`, `fat_per_serving`, optionally prefixed with `-` for descending order. The default SHALL be `name` ascending. The input schema SHALL list all fourteen accepted values as an enum.

#### Scenario: Sort by protein descending
- **WHEN** a client calls `list_recipes` with `sort` "-protein_per_serving"
- **THEN** recipes are returned from highest to lowest protein per serving

#### Scenario: Sort values are listed in the schema
- **WHEN** a client calls `tools/list`
- **THEN** the `sort` property of `list_recipes` has an `enum` containing exactly the seven keys and their seven `-` prefixed forms

### Requirement: Invalid list parameters are rejected
`list_recipes` SHALL reject these with a `validation_error` tool error: unknown sort keys, non-numeric bounds, ingredient lists that are not lists of strings, blank ingredient names, and a `limit` outside 1 to 200.

#### Scenario: Unknown sort key
- **WHEN** a client calls `list_recipes` with `sort` "tastiness"
- **THEN** the call returns a `validation_error` tool error

#### Scenario: Ingredient list given as an object
- **WHEN** a client calls `list_recipes` with `all_ingredients` set to `{"chicken": "all"}`
- **THEN** the call returns a `validation_error` tool error that identifies `all_ingredients`

## ADDED Requirements

### Requirement: Report unmatched ingredient names
`list_recipes` results SHALL include `unmatched_ingredients`: the normalized names from `all_ingredients` and `any_ingredients` that are not in the ingredient catalogue, without duplicates, in the order they were requested. The list SHALL be empty when every name is known or no ingredient filter was given.

#### Scenario: Unknown name is reported
- **WHEN** the catalogue has "chicken" and "peanut butter", and a client calls `list_recipes` with `all_ingredients` ["chicken", "peanut_butter"]
- **THEN** the result has no items and `unmatched_ingredients` is ["peanut_butter"]

#### Scenario: Known names report nothing
- **WHEN** a client calls `list_recipes` with `any_ingredients` ["chicken"] and "chicken" is in the catalogue
- **THEN** `unmatched_ingredients` is empty, whether or not any recipe matched
