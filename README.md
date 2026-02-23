# meeting-notes

Backend-first meeting intelligence API for:

- async document indexing (chunk + embed in background)
- grounded chat answers with citations
- meeting verification (decisions/actions/issues) with evidence IDs
- run-level observability for debugging and audits

## Current Status

Implemented in this repo today:

- FastAPI API in `apps/api/app/main.py`
- Postgres + `pgvector` for chunk storage/retrieval
- Redis + RQ for background indexing jobs
- Alembic migrations as the schema source of truth
- Guardrails for citation/evidence grounding
- Integration and unit test suite (`unittest`)
- GitHub Actions CI (runs migrations, then tests)

## Repository Layout

```text
meeting-notes/
  apps/api/
    app/
      ai/                  # OpenAI clients, embeddings, chat guardrails
      db/                  # SQLAlchemy models, engine/session, DB deps
      ingestion/           # text chunking utility
      jobs/                # background indexing + stale-processing reaper
      observability/       # run logging helpers
      schemas/             # request/response models
      verifier/            # verify engine (LLM + deterministic checks)
      main.py              # API endpoints/orchestration
      queue.py             # Redis/RQ queue helpers
      worker.py            # RQ worker entrypoint
    alembic/               # migration env + versions
    tests/                 # grounding/chat/verify/reliability tests
    requirements.txt
  infra/db/init.sql        # local DB extension bootstrap
  docker-compose.yml       # db + redis
  .github/workflows/tests.yml
```

## Architecture

### API Layer

- `POST /meetings/{meeting_id}/documents`:
  - creates `documents` row as `pending`
  - commits row first
  - enqueues indexing job
- `POST /meetings/{meeting_id}/chat`:
  - embeds question
  - retrieves top chunks by cosine distance
  - generates grounded answer
  - validates citations and retries once if invalid
- `POST /meetings/{meeting_id}/verify`:
  - loads meeting chunks (broad context)
  - extracts structured verify output
  - validates evidence IDs + deterministic issue checks
- `POST /documents/{document_id}/reindex`:
  - resets doc state to `pending`
  - re-enqueues indexing job
- `POST /internal/reaper/trigger`:
  - enqueues stale-processing cleanup job
  - optional header auth via `REAPER_TRIGGER_TOKEN`

### Worker / Queue Layer

- Queue config in `apps/api/app/queue.py`
  - deduped `job_id` for indexing jobs
  - timeout + retries with env-configured backoff
- Worker entrypoint in `apps/api/app/worker.py`
- Indexing job in `apps/api/app/jobs/indexing.py`
  - marks `processing`
  - chunks + embeds
  - writes new chunks first
  - marks `indexed`
  - best-effort deletes previous chunk set afterward (avoids zero-chunk downtime)
- Reaper job marks stale `processing` docs as `failed`

### AI / Guardrails Layer

- `apps/api/app/ai/embeddings.py`: batch embeddings (`text-embedding-3-small`)
- `apps/api/app/ai/client.py`: retrieval + grounded answer generation
- `apps/api/app/ai/grounding.py`: deterministic citation checks
  - disallow unknown chunk IDs
  - disallow missing/oversized quotes
  - require quote substring match in chunk text
- `apps/api/app/verifier/engine.py`:
  - strict JSON schema output
  - evidence ID validation + retry
  - deterministic issue rules (`missing_owner`, `missing_due_date`, `vague`)

### Observability Layer

`apps/api/app/observability/runs.py` writes one `runs` row per chat/verify call:

- retrieval ids
- model outputs (`response_json`)
- chat citations (`response_citations`)
- retry and invalid reason counts
- latency and model metadata

## Data Model

Main tables in `apps/api/app/db/models.py`:

- `meetings`
- `documents` (`status`, `error`, `processing_started_at`, `indexed_at`)
- `chunks` (`Vector(1536)` embedding)
- `runs` (`run_type`, retrieval ids, citations/json, retry metadata, latency, model info)

## Migrations (Alembic)

Alembic lives in `apps/api/alembic`.

- baseline: `20260222_0001_initial_schema.py`
- add `runs.response_json`: `20260222_0002_runs_response_json.py`

Commands (from `apps/api`):

```bash
./.venv/bin/alembic upgrade head
./.venv/bin/alembic revision --autogenerate -m "message"
./.venv/bin/alembic downgrade -1
```

If your local DB pre-dates Alembic and already has tables:

```bash
./.venv/bin/alembic stamp head
```

## API Endpoints

- `GET /health`
- `GET /`
- `GET /meetings`
- `POST /meetings`
- `GET /meetings/{meeting_id}`
- `POST /meetings/{meeting_id}/documents`
- `GET /meetings/{meeting_id}/documents`
- `GET /documents/{document_id}`
- `POST /documents/{document_id}/reindex`
- `POST /internal/reaper/trigger`
- `POST /meetings/{meeting_id}/chat`
- `POST /meetings/{meeting_id}/verify`

## Environment Variables

Core:

- `OPENAI_API_KEY`
- `DATABASE_URL` (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/meetingnotes`)
- `REDIS_URL` (default: `redis://localhost:6379/0`)
- `DEBUG_GROUNDING` (`true|false`)
- `REAPER_TRIGGER_TOKEN` (optional; protects reaper trigger endpoint)

Queue tuning:

- `INDEX_JOB_TIMEOUT_SECONDS` (default `900`)
- `INDEX_JOB_RETRY_MAX` (default `3`)
- `INDEX_JOB_RETRY_INTERVALS` (default `30,120,300`)
- `STALE_PROCESSING_MINUTES` (default `30`)

Example `apps/api/.env`:

```env
OPENAI_API_KEY="sk-..."
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/meetingnotes"
REDIS_URL="redis://localhost:6379/0"
DEBUG_GROUNDING="false"
REAPER_TRIGGER_TOKEN="change-me"
```

## Local Development

### 1) Start infra

From repo root:

```bash
docker compose up -d db redis
```

### 2) Install deps and run migrations

```bash
cd apps/api
./.venv/bin/pip install -r requirements.txt
set -a
source .env
set +a
./.venv/bin/alembic upgrade head
```

### 3) Start API

```bash
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4) Start worker (separate terminal)

```bash
cd apps/api
set -a
source .env
set +a
./.venv/bin/python -m app.worker
```

### 5) Optional scheduled reaper trigger

```bash
curl -X POST "http://127.0.0.1:8000/internal/reaper/trigger?max_age_minutes=30" \
  -H "x-reaper-token: ${REAPER_TRIGGER_TOKEN}"
```

## Tests

Run all tests:

```bash
cd apps/api
./.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

Coverage today includes:

- citation grounding unit tests
- chat integration tests
- verify integration tests
- indexing reliability tests (reindex + reaper + downtime regression)

## CI

Workflow: `.github/workflows/tests.yml`

Pipeline:

1. start Postgres (`pgvector/pgvector:pg16`)
2. install dependencies
3. run `alembic upgrade head`
4. run unit/integration tests

## Known Limitations

- No auth yet (all endpoints are open in local/dev).
- Reaper trigger is manual unless wired to cron/scheduler.
- Some timestamps still use `datetime.utcnow` (deprecation cleanup pending).

## Near-Term Next Steps

- add auth + user/workspace model
- add frontend for meetings/documents/chat/verify
- add reaper scheduler in deployment
- migrate FastAPI startup to lifespan
- tighten timestamp handling to timezone-aware defaults throughout
