# Multi-Tenant User Directory

This project implements Assignment 1 using Python with SOLID-oriented boundaries, unit tests, `Pipfile` environment management, and Docker/Docker Compose for reproducibility.

## Architecture

The design intentionally separates responsibilities:

- `domain/`: immutable business entities.
- `ports/`: repository and store abstractions.
- `services/`: orchestration for registration, billing, sharding, reporting, and replication.
- `infrastructure/`: SQLite-backed relational persistence plus a key-value session store implementation.

### SQL vs. NoSQL decision

- Relational storage: billing and user directory records live in SQLite in this reference implementation because those operations need transactions, foreign keys, and consistency guarantees that mirror a production PostgreSQL choice.
- Key-value storage: sessions use a `SessionStore` abstraction with a real Redis-backed implementation for the app runtime and an in-memory implementation for tests.

### Sharding strategy

- Tenants are partitioned with application-level sharding.
- `HashTenantShardStrategy` deterministically maps `tenant_id` to a shard id.
- Writes and transactional reads go only to that tenant's primary shard.

### Replication strategy

- Primary databases handle writes.
- Replica databases serve analytics/reporting reads.
- `ReplicationService` synchronizes each primary shard to its replica counterpart.
- `AnalyticsReportService` only reads from replica repositories, protecting primaries from heavy report traffic.

## Data model

Relational tables per shard:

- `users(tenant_id, user_id, email, full_name, is_active)`
- `billing_accounts(tenant_id, user_id, balance, currency)`

Key-value shape for sessions:

- `session_id -> {tenant_id, user_id, payload}`

## Run locally

```bash
python -m unittest discover -s tests -v
python -m src.multi_tenant_directory.main
```

## Run with Pipenv

```bash
pipenv install --dev
pipenv run python -m unittest discover -s tests -v
pipenv run python -m src.multi_tenant_directory.main
```

## Run with Docker

```bash
docker compose up --build
```

The app writes shard databases to `./data`.

## Python Version

The project targets Python 3.14 consistently across Pipenv, Docker, and static type checking.
