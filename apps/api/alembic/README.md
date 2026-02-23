# Alembic Migrations

Run commands from `apps/api`:

```bash
./.venv/bin/alembic upgrade head
```

If your DB was created before Alembic adoption and tables already exist, do this once first:

```bash
./.venv/bin/alembic stamp head
```

Create a new migration after model changes:

```bash
./.venv/bin/alembic revision --autogenerate -m "describe change"
```

Apply one step down (rollback):

```bash
./.venv/bin/alembic downgrade -1
```

Notes:
- `DATABASE_URL` is read from env (`.env`).
- `pgvector` extension is created in the baseline migration.
