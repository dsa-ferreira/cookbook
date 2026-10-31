# Spec Delta

## MODIFIED Requirements

### Requirement: Bearer API key required
Every HTTP request except the health check, including every request to the MCP endpoint, SHALL require an `Authorization: Bearer <key>` header whose key matches one of the configured keys. A missing, malformed or unknown key SHALL be rejected with status 401 and a JSON error body, before any MCP message is processed.

#### Scenario: Valid key
- **WHEN** a client sends a `tools/call` request for `list_recipes` to `/mcp` with a configured key
- **THEN** the request is processed normally

#### Scenario: Missing key
- **WHEN** a client sends an `initialize` request to `/mcp` without an Authorization header
- **THEN** the response has status 401

#### Scenario: Unknown key
- **WHEN** a client sends a `tools/call` request for `create_recipe` to `/mcp` with a key that is not configured
- **THEN** the response has status 401 and no recipe is created

### Requirement: Authenticated key name is logged
The name of the authenticated key SHALL be recorded in the request log for each authenticated request. Each tool call SHALL also be logged with the tool name and the key name. The key itself and its hash SHALL NOT be logged.

#### Scenario: Request attribution
- **WHEN** a request is made with the key named `diogo`
- **THEN** the request log entry includes `diogo` and does not include the key

#### Scenario: Tool call attribution
- **WHEN** the key named `openwebui` is used to call `delete_recipe`
- **THEN** the log records `delete_recipe` together with `openwebui`, and does not include the key
