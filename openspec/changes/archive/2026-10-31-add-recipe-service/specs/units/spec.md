# Spec Delta

## Purpose

Defines the curated vocabulary of measurement units. Each unit has a dimension and a conversion to its base unit, so ingredient quantities stay consistent and can later be summed.

## ADDED Requirements

### Requirement: Curated unit vocabulary
The system SHALL provide a fixed set of units. Each unit has a lowercase code, a dimension (`mass`, `volume` or `count`) and a conversion factor to the dimension's base unit (gram, millilitre or one item). The initial set SHALL be: g (1), kg (1000), ml (1), l (1000), tsp (5), tbsp (15), cup (240), piece (1), clove (1), can (1), pinch (1).

#### Scenario: Mass conversion factor
- **WHEN** a client reads the unit `kg`
- **THEN** its dimension is `mass` and its factor to base is 1000

#### Scenario: Kitchen volume unit
- **WHEN** a client reads the unit `tbsp`
- **THEN** its dimension is `volume` and its factor to base is 15

### Requirement: List units
`GET /units` SHALL return every unit with its code, dimension and factor to base.

#### Scenario: Units are discoverable
- **WHEN** a client requests `GET /units`
- **THEN** the response includes `g`, `ml` and `clove` with their dimensions and factors

### Requirement: Unknown units are rejected
A recipe whose ingredient lines use a unit code that is not in the vocabulary SHALL be rejected with status 422, and the error SHALL name the unknown code. Units SHALL NOT be created implicitly by recipe writes.

#### Scenario: Unknown unit code
- **WHEN** a client creates a recipe with an ingredient line using unit `handful`
- **THEN** the request is rejected with status 422 naming `handful`, and no unit `handful` exists afterwards
