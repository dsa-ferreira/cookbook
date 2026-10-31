# Spec Delta

## Purpose

Restricts the recipe API to holders of configured API keys. Each person gets a named key, without any user management.

## ADDED Requirements

### Requirement: Bearer API key required
Every API endpoint except the health check SHALL require an `Authorization: Bearer <key>` header whose key matches one of the configured keys. A missing, malformed or unknown key SHALL be rejected with status 401 and a JSON error body, before any request processing.

#### Scenario: Valid key
- **WHEN** a client calls `GET /recipes` with a configured key
- **THEN** the request is processed normally

#### Scenario: Missing key
- **WHEN** a client calls `GET /recipes` without an Authorization header
- **THEN** the response has status 401

#### Scenario: Unknown key
- **WHEN** a client calls `POST /recipes` with a key that is not configured
- **THEN** the response has status 401 and no recipe is created

### Requirement: Health check is unauthenticated
`GET /healthz` SHALL respond with status 200 without requiring a key, and SHALL NOT expose any recipe data.

#### Scenario: Health check without key
- **WHEN** a client calls `GET /healthz` without an Authorization header
- **THEN** the response has status 200

### Requirement: Named keys configured as hashes
API keys SHALL be configured as a mapping from a key name to the SHA-256 hash of the key, so that the service configuration never contains a usable key in plaintext. Each key SHALL be revocable independently by removing its entry and restarting the service.

#### Scenario: Revoking one key
- **WHEN** the entry for one key name is removed from configuration and the service restarts
- **THEN** requests with that key get status 401 while the other configured key still works

### Requirement: Authenticated key name is logged
The name of the authenticated key SHALL be recorded in the request log for each authenticated request. The key itself and its hash SHALL NOT be logged.

#### Scenario: Request attribution
- **WHEN** a request is made with the key named `diogo`
- **THEN** the request log entry includes `diogo` and does not include the key
