# Alembic Migrations

Run commands from `apps/api`.

## Apply Latest

```bash
./.venv/bin/alembic upgrade head
```

## If DB Already Existed Before Alembic

```bash
./.venv/bin/alembic stamp head
```

## Create New Migration

```bash
./.venv/bin/alembic revision --autogenerate -m "describe change"
```

## Roll Back One Revision

```bash
./.venv/bin/alembic downgrade -1
```

## Current Revisions

- `20260222_0001_initial_schema`
- `20260222_0002_runs_response_json`
- `20260223_0003_documents_file_metadata`

Notes:
- `DATABASE_URL` comes from env.
- `pgvector` extension is created in baseline migration.
