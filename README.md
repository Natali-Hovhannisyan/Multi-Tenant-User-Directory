# ShardDirectory: Multi-Tenant User Directory

Python reference implementation for Assignment 1 with:

- relational user and billing storage
- Redis-backed session storage
- tenant-based sharding
- primary/replica reporting
- Docker reproducibility
- unit and integration tests
- logging, linting, formatting, and type checking

## Assignment Mapping

- Data modeling:
  `users` and `billing_accounts` use a relational model because billing needs transactional consistency.
- NoSQL:
  sessions are stored in Redis for fast key-value lookup.
- Sharding:
  `tenant_id` is hashed to a shard so a tenant only hits one database shard.
- Replication:
  reporting reads are served from replica shard databases instead of primaries.

## Architecture

- `src/multi_tenant_directory/domain/`
  domain entities
- `src/multi_tenant_directory/ports/`
  repository and store abstractions
- `src/multi_tenant_directory/services/`
  sharding, directory, reporting, replication, bootstrap
- `src/multi_tenant_directory/infrastructure/`
  SQLite repositories and Redis session store

## Data Model

Relational tables per shard:

- `users(tenant_id, user_id, email, full_name, is_active)`
- `billing_accounts(tenant_id, user_id, balance, currency)`

Redis session shape:

- `session_id -> {"session_id", "tenant_id", "user_id", "payload"}`

## Python Version

The project targets Python 3.14 across:

- `Pipfile`
- `Dockerfile`
- `mypy.ini`

## Dependencies

Runtime:

- `redis`

Development:

- `pytest`
- `ruff`
- `black`
- `mypy`

## Local Setup

Install dependencies:

```bash
pipenv install --dev
```

Useful commands:

```bash
pipenv run test
pipenv run lint
pipenv run typecheck
pipenv run format
pipenv run format-check
pipenv run quality
```

## CLI Usage

Default local run:

```bash
pipenv run python -m src.multi_tenant_directory.main
```

This runs the default `demo` mode for one tenant and one user.

Custom demo run:

```bash
pipenv run python -m src.multi_tenant_directory.main demo \
  --tenant-id tenant-acme \
  --user-id user-001 \
  --email owner@acme.example \
  --full-name "Acme Owner" \
  --starting-balance 100.00 \
  --charge-amount 19.99 \
  --session-id session-001 \
  --session-payload '{"role":"owner"}'
```

Load test run:

```bash
pipenv run python -m src.multi_tenant_directory.main load-test \
  --tenant-count 10 \
  --users-per-tenant 20 \
  --workers 8 \
  --starting-balance 100.00 \
  --charge-amount 5.00
```

## Docker

Build and run the full stack:

```bash
docker compose up --build
```

Docker Compose is configured to run the `load-test` CLI by default, not the single-tenant demo.

Current Compose workload:

- `5` tenants
- `10` users per tenant
- `4` workers
- starting balance `100.00`
- charge amount `5.00`

This starts:

- the Python app
- Redis

Stop it with:

```bash
docker compose down
```

If you want a clean rerun:

```bash
docker compose down
rm -f data/*.db
docker compose up --build
```

The shard database files are written to:

```text
./data
```

## Automated Testing

Run the automated suite:

```bash
python3 -m unittest discover -s tests -v
```

The tests cover:

- shard routing
- billing updates
- duplicate protection
- replica reads
- replication failures
- session-store behavior
- Redis session serialization

## How To Test Everything

### 1. Run automated tests

From the project root:

```bash
pipenv install --dev
pipenv run test
```

Optional quality checks:

```bash
pipenv run lint
pipenv run typecheck
pipenv run format-check
```

### 2. Run a local custom demo

```bash
pipenv run python -m src.multi_tenant_directory.main demo \
  --tenant-id tenant-demo \
  --user-id user-demo \
  --email demo@example.com \
  --full-name "Demo User" \
  --starting-balance 120.00 \
  --charge-amount 20.00 \
  --session-id session-demo \
  --session-payload '{"role":"tester"}'
```

Expected result:

- the command prints a tenant report line
- shard DB files appear in `data/`

### 3. Run a lightweight local load test

```bash
rm -f data/*.db
pipenv run python -m src.multi_tenant_directory.main load-test \
  --tenant-count 5 \
  --users-per-tenant 10 \
  --workers 4
```

Expected result:

- the command prints operations, elapsed time, and throughput
- multiple tenants are distributed across shard files

### 4. Run full Docker Compose end-to-end validation

```bash
docker compose down
rm -f data/*.db
docker compose up --build
```

Expected behavior:

- the app runs the load-test workload
- tenant data is distributed across both primary shards
- replica shards contain corresponding billing data
- Redis contains many session keys

### 5. Verify shard distribution

In a second terminal:

```bash
sqlite3 data/primary-shard-0.db "SELECT tenant_id, user_id, email, full_name, is_active FROM users;"
sqlite3 data/primary-shard-1.db "SELECT tenant_id, user_id, email, full_name, is_active FROM users;"
```

Expected result:

- multiple tenants exist
- tenants are split across the two shard databases

### 6. Verify billing and replication

```bash
sqlite3 data/replica-shard-0.db "SELECT tenant_id, user_id, balance FROM billing_accounts;"
sqlite3 data/replica-shard-1.db "SELECT tenant_id, user_id, balance FROM billing_accounts;"
```

For the default Docker Compose workload, each balance should be:

```text
105.00
```

because the load test uses:

- starting balance `100.00`
- charge amount `5.00`

### 7. Verify Redis session storage

```bash
docker compose exec redis redis-cli
```

Inside Redis CLI:

```bash
KEYS *
```

Expected result for the default Docker Compose workload:

- `50` session keys total
- session keys like `session-0004-0005`

This matches:

- `5 tenants × 10 users = 50 sessions`

## Logging and Error Handling

The app includes `INFO`, `DEBUG`, and `ERROR` logging and uses specific application exceptions instead of broad catch-all handling.

Examples:

- `ShardNotFoundError`
- `UserAlreadyExistsError`
- `BillingAccountNotFoundError`
- `DataAccessError`
- `ReplicationError`
- `SessionStoreError`

## Notes

- SQLite is used here as a runnable stand-in for PostgreSQL.
- Redis is the real NoSQL component used by the runtime.
- Integration tests use the in-memory session backend so tests stay fast and isolated.
- `docker-compose.yml` still contains a deprecated `version` field warning; it does not block functionality.
