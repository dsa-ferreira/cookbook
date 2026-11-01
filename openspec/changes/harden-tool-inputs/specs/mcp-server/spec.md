# Spec Delta

## ADDED Requirements

### Requirement: Unknown tool arguments are rejected
Each tool's input schema SHALL declare `additionalProperties: false` at the top level. A call that sends an argument the tool does not declare SHALL fail with a `validation_error` tool error whose details name every undeclared argument. The tool SHALL NOT run.

#### Scenario: Misnamed filter is rejected
- **WHEN** a client calls `list_recipes` with `{"min_kcal": 100}`
- **THEN** the result has `isError` true, code `validation_error`, and its details identify `min_kcal`

#### Scenario: Every undeclared argument is named
- **WHEN** a client calls `get_recipe` with `{"recipe_id": 1, "verbose": true, "fields": ["name"]}`
- **THEN** the `validation_error` details identify both `verbose` and `fields`

#### Scenario: Schema forbids extra arguments
- **WHEN** a client calls `tools/list`
- **THEN** every tool's input schema has `additionalProperties` set to false

### Requirement: Tool arguments are described
Every argument of every tool SHALL have a description in the tool's input schema. This includes fields of nested input objects. Where the name alone could be misread, the description SHALL state the unit, whether a value is per serving or for the whole recipe, and the expected format.

#### Scenario: All arguments carry descriptions
- **WHEN** a client calls `tools/list`
- **THEN** every property in every tool's input schema, including those in nested definitions, has a non-empty description

#### Scenario: Macro bound states its unit
- **WHEN** a client reads the input schema of `list_recipes`
- **THEN** the description of `min_protein_per_serving` says the value is in grams per serving

### Requirement: Rejected calls are logged
The server SHALL log every tool call that ends in a `validation_error` at WARNING level. The entry SHALL include the tool name, the names of the arguments sent, and the error details (location, type and message of each error). It SHALL NOT include argument values.

#### Scenario: Validation failure is logged
- **WHEN** a client calls `list_recipes` with `ingredients` set to `{"chicken": "all"}`
- **THEN** a WARNING log entry names `list_recipes`, lists the argument name `ingredients`, and includes the error details

#### Scenario: Argument values stay out of the log
- **WHEN** a client calls `create_recipe` with a recipe whose `servings` is 0
- **THEN** the WARNING entry identifies `recipe.servings` and does not contain the recipe's name, steps or other values
