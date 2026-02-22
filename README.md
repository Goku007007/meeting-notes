# meeting-notes

AI-assisted meeting workspace that turns notes into grounded answers with citations.

This repository is being built toward a full product (users, frontend, collaboration).  
Current implementation is backend-first and focuses on ingestion, retrieval, guardrails, and observability.

## Product Vision

`meeting-notes` is intended to become a full application where users can:

- create and manage meetings
- upload/paste notes/transcripts
- ask questions over meeting content
- get citation-backed answers
- audit how answers were produced

Target product areas (in progress/planned):

- user accounts and authentication
- frontend application (dashboard + chat UI)
- team/project-level collaboration
- richer retrieval and analytics

## Current Scope (Implemented Today)

Backend API currently supports:

- meeting creation and lookup
- document ingestion into meetings
- chunk generation + embedding storage (`pgvector`)
- retrieval scoped by `meeting_id`
- grounded chat responses with citation guardrails
- one-retry guardrail path and safe fallback
- per-chat run logging (`runs` table) for debugging/audit
- unit + integration tests
- CI test workflow on push/PR

## Repository Structure

```text
meeting-notes/
  apps/
    api/
      app/
        ai/                # embeddings, retrieval, grounding logic
        db/                # models, engine/session, DB deps
        ingestion/         # text chunking
        observability/     # run logging helper
        schemas/           # request/response models
        main.py            # FastAPI app + route orchestration
      tests/               # unit + integration tests
      requirements.txt
  infra/
    db/init.sql            # DB initialization for local Docker
  docker-compose.yml
  .github/workflows/tests.yml
```

## Backend Architecture

### API Layer

- `apps/api/app/main.py`
  - route handlers
  - ingestion orchestration
  - chat orchestration
  - startup DB/table initialization

### AI Layer

- `apps/api/app/ai/embeddings.py`
  - batched embedding generation (`text-embedding-3-small`)
- `apps/api/app/ai/client.py`
  - vector retrieval
  - grounded response generation
  - citation validation + retry metadata
- `apps/api/app/ai/grounding.py`
  - deterministic citation validation rules

### Data Layer

- `apps/api/app/db/models.py`
  - `Meeting`, `Document`, `Chunk`, `Run`
- `apps/api/app/db/session.py`
  - async engine/session factory
  - `DATABASE_URL` env support
- `apps/api/app/db/deps.py`
  - FastAPI DB dependency

### Observability Layer

- `apps/api/app/observability/runs.py`
  - centralized `log_chat_run(...)` helper

## Data Model (Current)

- `meetings`: meeting metadata
- `documents`: source documents per meeting
- `chunks`: chunked text + embedding vectors
- `runs`: per-chat audit records (question, retrieved IDs, citations, retry/invalid metadata, latency, model names)

## Request Flows

### Ingestion Flow (`POST /meetings/{meeting_id}/documents`)

1. validate meeting exists
2. create `Document`
3. chunk raw text
4. embed all chunks in one batch
5. insert `Chunk` rows with embeddings
6. commit once
7. rollback on failure

### Chat Flow (`POST /meetings/{meeting_id}/chat`)

1. embed question
2. retrieve top-k similar chunks in same meeting
3. call model with context and strict JSON schema response format
4. validate citations against retrieved chunk allowlist
5. retry once with stricter citation rules if needed
6. fallback to safe answer with empty citations if still invalid
7. write one run row (best effort; does not block response if logging fails)

## Guardrails and Reliability

Citation validator rejects:

- chunk IDs not in retrieved set
- missing quotes
- overly long quotes
- quotes not present in cited chunk text (normalized matching)

This keeps citation output deterministic and auditable.

## Observability

`runs` table provides a "black-box recorder" for chat requests:

- input question
- retrieved chunk IDs
- output citations
- retry happened or not
- invalid citation reason counts
- latency in ms
- model + embedding model names

This is the main debugging trail when an answer looks wrong.

## API Endpoints (Current)

- `GET /health`
- `GET /`
- `POST /meetings`
- `GET /meetings/{meeting_id}`
- `POST /meetings/{meeting_id}/documents`
- `POST /meetings/{meeting_id}/chat`

## Environment Variables

- `OPENAI_API_KEY` (required for embedding/model calls)
- `DATABASE_URL` (optional locally, required in most CI/prod setups)
- `DEBUG_GROUNDING` (`true/false`, optional verbose grounding logs)

Example `apps/api/.env`:

```env
OPENAI_API_KEY="sk-..."
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/meetingnotes"
DEBUG_GROUNDING="false"
```

## Local Development

### 1) Start infra

From repo root:

```bash
docker compose up -d db redis
```

### 2) Start API

```bash
cd apps/api
set -a
source .env
set +a
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3) Run tests

```bash
cd apps/api
./.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

## CI

Workflow: `/.github/workflows/tests.yml`

- runs on push + pull_request
- starts Postgres (`pgvector/pgvector:pg16`)
- installs API dependencies
- runs test suite (`unittest discover`)

## Roadmap (Near-Term)

### Backend

- migrate from `create_all` to Alembic migrations
- move startup event to FastAPI lifespan pattern
- improve timestamp handling (`datetime.utcnow` deprecation cleanup)
- add pagination/filtering for meetings/documents/runs

### Product Features

- add users/auth (session/JWT/OAuth)
- add multi-user access control per meeting/workspace
- build frontend (meeting list, document upload, chat UI, run inspection)
- add feedback loop for answer quality and retrieval tuning

## Notes

This README is intentionally product-level and forward-looking.  
It documents both:

- what is implemented now
- what the application is expected to become

As the frontend and user system are added, update this file first so architecture and scope stay explicit.
