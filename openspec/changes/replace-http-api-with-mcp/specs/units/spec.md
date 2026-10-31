# Spec Delta

## MODIFIED Requirements

### Requirement: List units
The `list_units` tool SHALL return every unit with its code, dimension and factor to base.

#### Scenario: Units are discoverable
- **WHEN** a client calls `list_units`
- **THEN** the result includes `g`, `ml` and `clove` with their dimensions and factors

### Requirement: Unknown units are rejected
A recipe whose ingredient lines use a unit code that is not in the vocabulary SHALL be rejected with a `validation_error` tool error, and the error SHALL name the unknown code. Units SHALL NOT be created implicitly by recipe writes.

#### Scenario: Unknown unit code
- **WHEN** a client calls `create_recipe` with an ingredient line using unit `handful`
- **THEN** the call returns a `validation_error` tool error naming `handful`, and no unit `handful` exists afterwards
