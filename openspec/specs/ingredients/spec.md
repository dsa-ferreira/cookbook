# ingredients Specification

## Purpose

Maintains one canonical catalogue of ingredients shared by all recipes, so the same ingredient is recognized across recipes. Shopping lists and ingredient filtering depend on this.

## Requirements

### Requirement: Ingredient name normalization
Ingredient names SHALL be normalized by trimming surrounding whitespace, collapsing internal whitespace to single spaces and lowercasing. Two names that normalize to the same value SHALL refer to the same ingredient. An empty normalized name SHALL be rejected with status 422.

#### Scenario: Case and whitespace variants are one ingredient
- **WHEN** one recipe uses "Chickpeas" and another uses "  chickpeas "
- **THEN** both ingredient lines refer to the single catalogue ingredient "chickpeas"

#### Scenario: Blank name is rejected
- **WHEN** a recipe contains an ingredient line whose name is "   "
- **THEN** the request is rejected with status 422

### Requirement: Get-or-create on recipe write
When a recipe is created or replaced, each ingredient line's name SHALL resolve to the existing catalogue ingredient with that normalized name. If none exists, a new ingredient SHALL be created. This SHALL happen in the same transaction as the recipe write.

#### Scenario: New ingredient is created
- **WHEN** a recipe is created with an ingredient named "za'atar" that is not in the catalogue
- **THEN** "za'atar" is added to the catalogue

#### Scenario: Existing ingredient is reused
- **WHEN** "garlic" is already in the catalogue and a new recipe uses "Garlic"
- **THEN** no new ingredient is created and the line refers to the existing "garlic"

#### Scenario: Rejected recipe creates no ingredients
- **WHEN** a recipe with a new ingredient "sumac" is rejected because of an unknown unit
- **THEN** "sumac" is not added to the catalogue

### Requirement: Ingredient search
`GET /ingredients` SHALL return catalogue ingredients ordered by name, each with its id and name. An optional `q` parameter SHALL restrict results to names containing `q` case-insensitively. Results SHALL be paginated with `limit` (default 50, maximum 200) and `offset`.

#### Scenario: Substring search
- **WHEN** the catalogue contains "chickpeas", "chickpea flour" and "spinach" and a client requests `GET /ingredients?q=Chick`
- **THEN** "chickpea flour" and "chickpeas" are returned and "spinach" is not

#### Scenario: List without query
- **WHEN** a client requests `GET /ingredients` with no `q`
- **THEN** catalogue ingredients are returned in name order, up to the default limit
