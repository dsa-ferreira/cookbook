# cookbook handover

cookbook is a small recipe store with a JSON HTTP API. It stores recipes with
steps, structured ingredient lines, timing and macros. Its only client is an AI
assistant on the LAN that calls it over raw HTTP with a bearer API key. The
household has two users and no browser UI.

```yaml
handover: 1
service:
  name: cookbook
  summary: Recipe store with a JSON HTTP API for an AI assistant
  source: https://github.com/dsa-ferreira/cookbook
  release: 0.1.0

placement:
  preference: any
  reason: One small Flask/gunicorn container plus a Postgres database. Light load (two users, one assistant client).

exposure:
  hostname: cookbook.lan
  tailnet: false
  who_calls_it: [AI assistant clients on the LAN (raw HTTP, bearer key)]

components:
  - name: api
    image: album.lan/cookbook:0.1.0          # built (linux/amd64) but NOT pushed yet, see Open questions
    kind: service
    user: "10001:10001"                      # no volumes, so this doesn't matter for permissions
    ports:
      - port: 8080
        protocol: http
        purpose: JSON API (every path except /healthz needs a bearer key)
        public: true
    env:
      COOKBOOK_DATABASE_URL: {from: dependency, name: db, field: url}
      COOKBOOK_API_KEYS: {from: secret, name: api_keys}
    healthcheck:
      http: {path: /healthz, port: 8080, expect: 200}   # process liveness only; does not touch the DB
      start_period: 15s
    resources:
      cpu: TODO                             # not measured; 2 gunicorn sync workers
      memory: TODO                          # not measured
      gpu: none
    depends_on: [db]

dependencies:
  - name: db
    type: postgres
    version: "17"                           # tested on 17 only
    needs:
      extensions: []
      databases: [cookbook]
      privileges: owner of the cookbook database (creates its tables on start); no superuser
    size: TODO                              # text-only recipes for two users; not measured
    backup: required
    shareable: true
    clients_reach_directly: false
    fields:
      url: postgresql://<user>:<password>@<host>:5432/cookbook

secrets:
  - name: db_password
    generate: hex32
    used_by: [api]                          # embedded in COOKBOOK_DATABASE_URL
    rotation: Change it in Postgres and in the URL together, then restart api.
  - name: api_keys
    generate: user_provided
    used_by: [api]
    rotation: >-
      JSON object {"<key name>": "<sha256 hex of the key>"}. It holds hashes
      only, never the keys. A key stops working when its entry is removed
      and api restarts. Clients whose entry changes need the new plaintext key.

integrations: []

lifecycle:
  migrations: on_start                      # the entrypoint runs `cookbook migrate` (alembic upgrade head) before gunicorn
  first_run:
    - Create the cookbook database and its owner role in Postgres.
    - Generate one API key per user (see First run) and put the hashes in the api_keys secret.
    - Start api. Migrations create the schema and seed the unit table.
  upgrade: pg_dump the database before deploying a release that contains new migrations. The image has no downgrade command, so rolling back means restoring that dump.
  restart_safe: true

verify:
  - "curl -s https://cookbook.lan/healthz  →  {\"status\": \"ok\"}"
  - "curl -s -o /dev/null -w '%{http_code}' https://cookbook.lan/units  →  401"
  - "curl -s -H 'Authorization: Bearer <key>' https://cookbook.lan/units  →  200 and JSON with 11 items (g, kg, ml, l, tsp, tbsp, cup, piece, clove, can, pinch); this proves auth, DB access and migrations"
```

## Configuration

All configuration comes from `COOKBOOK_*` environment variables. There are no
config files. The service validates them at startup and exits with an error that
names the bad variable without printing its value.

- `COOKBOOK_DATABASE_URL` (required). A libpq-style `postgresql://` or
  `postgres://` URL. The service rewrites it to use psycopg 3. A password
  containing URL-special characters must be percent-encoded, so `hex32` is the
  simplest choice.
- `COOKBOOK_API_KEYS` (required for the API, not for `migrate`). A JSON object
  that maps key names to lowercase 64-character SHA-256 hex digests. **The
  service refuses to start if this is empty or missing**, so a misconfigured
  deploy can't come up open. The value contains `{`, `"` and `:`, so quote it
  properly in the `.env` template.
- `GUNICORN_CMD_ARGS`. The image sets it to
  `--bind=0.0.0.0:8080 --workers=2 --no-control-socket`. Keep the default. If
  you override it, keep the bind on 8080.

Requests are small JSON documents and finish quickly, so the proxy defaults
(1m body, 60s) are enough. Logs go to stdout/stderr. Each request is logged with
the key *name*, never the key.

## Data and backups

All state lives in the `cookbook` Postgres database. The api container is
stateless and has no volumes. The data is hand-entered and can't be
regenerated, so backups are **required**.

- Backup: `pg_dump -Fc cookbook` while the service is running. A single dump
  is consistent.
- Restore: `pg_restore` into an empty `cookbook` database owned by the service
  role, then start api. The migrations on start find the schema already at
  head and do nothing.
- Also take a dump just before any upgrade that adds migrations. There is no
  downgrade command in the image.

## First run

The API keys are created outside the vault's random generator because each
plaintext key goes to a client. Each user needs their own key. Run this once per
user from any host that can pull the image. Override the entrypoint, because the
default entrypoint runs migrations first:

```sh
docker run --rm --entrypoint cookbook album.lan/cookbook:0.1.0 apikey <name>
```

The output shows the plaintext key once, plus a `"<name>": "<hash>"` line.
Collect the lines into one JSON object and store it as the `api_keys` secret.
Give each plaintext key to whoever configures that user's assistant. It does not
go into the cookbook deployment.

## Open questions

- **Image not pushed.** `album.lan/cookbook:0.1.0` returns "manifest unknown".
  It is built locally for linux/amd64 and needs `make push` before deploy.
  There is no git tag for 0.1.0 yet either.
- **Resources** (`components.api.resources.cpu/memory`): these have not been
  measured. The service runs 2 gunicorn sync workers on Python 3.13 with light
  traffic. Should the infra side use its small-service defaults?
- **Database size** (`dependencies.db.size`): this has not been measured. It
  holds text-only recipes for two users, so it should stay small.

## Not covered

- MCP server and OpenAPI spec. Both are planned but not built, so open-webui
  can't use cookbook as a tool yet. A later release will add an integration.
- Metrics, tailnet access and email are not covered. The service needs none of
  them.
