# Backend API Contract for Frontend/Agent Design

This file is the frontend-facing backend source of truth for the current codebase.

Scope:
- API routes and exact request/response shapes
- Error behavior and status codes
- Document/indexing state machine
- Database schema relevant to frontend behavior
- Known gaps/quirks the frontend should handle

Codebase source:
- `apps/api/app/main.py`
- `apps/api/app/schemas/*.py`
- `apps/api/app/db/models.py`
- `apps/api/app/jobs/indexing.py`
- `apps/api/app/verifier/engine.py`

## 1) Global Contract

- Base URL (local): `http://127.0.0.1:8000`
- OpenAPI docs: `GET /docs`
- Auth: none (all routes currently open)
- IDs: UUID strings
- Content-Type: JSON for body-based endpoints
- Error format: FastAPI style `{"detail":"..."}`

## 2) Core Domain Objects

### Meeting
- `id: string (uuid)`
- `title: string`
- `created_at` stored in DB (not returned by APIs currently)

### Document
- `id: string (uuid)`
- `meeting_id: string (uuid)`
- `doc_type: string`
- `filename: string | null`
- `raw_text: string`
- `status: "pending" | "processing" | "indexed" | "failed"`
- `error: string | null`
- `processing_started_at: datetime | null`
- `indexed_at: datetime | null`

### Chunk
- `id: string (uuid)`
- `meeting_id: string (uuid)`
- `document_id: string (uuid)`
- `chunk_index: int`
- `text: string`
- `embedding: vector(1536) | null`

### Run (observability)
- `id: string (uuid)`
- `meeting_id: string (uuid)`
- `run_type: "chat" | "verify" (string)`
- `input_text: string`
- `retrieved_chunk_ids: string[]`
- `response_citations: object[]`
- `response_json: object | null`
- `had_retry: bool`
- `invalid_citation_reasons: object`
- `latency_ms: int`
- `model: string`
- `embedding_model: string`

## 3) API Endpoints

## 3.1 Health / Root

### `GET /health`
- Response `200`:
```json
{"ok": true}
```

### `GET /`
- Response `200`:
```json
{"message":"API is running try /health or /docs"}
```

## 3.2 Meetings

### `POST /meetings?title=<title>`
Creates a meeting. `title` is a query parameter (not JSON body).

- Success `200`:
```json
{"id":"<uuid>","title":"<title>"}
```

### `GET /meetings`
Returns all meetings ordered by newest first.

- Success `200`:
```json
[
  {"id":"<uuid>","title":"Meeting A"},
  {"id":"<uuid>","title":"Meeting B"}
]
```

### `GET /meetings/{meeting_id}`
- Success `200`:
```json
{"id":"<uuid>","title":"..."}
```
- Not found: `404 {"detail":"meeting not found"}`

## 3.3 Documents / Indexing

### `POST /meetings/{meeting_id}/documents`
Creates a document row and enqueues background indexing.

Request body:
```json
{
  "doc_type": "notes",
  "filename": "m1.txt",
  "text": "raw notes/transcript content"
}
```

Validation:
- `doc_type`: required, `1..50` chars
- `filename`: optional, max `255`
- `text`: required, min length `1`

Success `200`:
```json
{
  "document_id":"<uuid>",
  "status":"pending"
}
```

Errors:
- `404 {"detail":"meeting not found"}`
- `500 {"detail":"failed to enqueue indexing job"}`

### `GET /meetings/{meeting_id}/documents`
Lists documents for a meeting, newest first.

Success `200`:
```json
[
  {
    "document_id":"<uuid>",
    "meeting_id":"<uuid>",
    "doc_type":"notes",
    "filename":"m1.txt",
    "status":"pending|processing|indexed|failed",
    "error": null,
    "processing_started_at": null,
    "indexed_at": null
  }
]
```

Error:
- `404 {"detail":"meeting not found"}`

### `GET /documents/{document_id}`
Fetch status for polling.

Success `200`:
```json
{
  "document_id":"<uuid>",
  "status":"pending|processing|indexed|failed",
  "error": null,
  "processing_started_at": null,
  "indexed_at": null
}
```

Error:
- `404 {"detail":"document not found"}`

### `POST /documents/{document_id}/reindex`
Resets document and re-enqueues indexing.

Success `200`:
```json
{
  "document_id":"<uuid>",
  "status":"pending"
}
```

Errors:
- `404 {"detail":"document not found"}`
- `409 {"detail":"document is already processing"}`
- `500 {"detail":"failed to enqueue indexing job"}`

## 3.4 Chat

### `POST /meetings/{meeting_id}/chat`
Request:
```json
{"question":"What did we decide?"}
```

Validation:
- `question` min length `1`

Success `200` (always schema-consistent):
```json
{
  "answer":"...",
  "citations":[
    {"chunk_id":"<uuid>","quote":"..."}
  ]
}
```

Possible answer modes:
- grounded answer with citations
- indexing-in-progress message:
  - `"This meeting is still being indexed. Try again in a moment."`
- no-support fallback:
  - `"I don't know based on the provided context."` or
  - `"I don't know based on the provided notes."`

Errors:
- `404 {"detail":"meeting not found"}`
- `500 {"detail":"failed to embed question"}`

Grounding behavior:
- citations are validated against retrieved chunk IDs and chunk text
- one retry with stricter citation constraints
- if still invalid, response returns empty citations with safe fallback answer

## 3.5 Verify

### `POST /meetings/{meeting_id}/verify`
No request body.

Success `200`:
```json
{
  "structured_summary":"...",
  "decisions":["..."],
  "action_items":[
    {
      "task":"...",
      "owner":"...",
      "due_date":"...",
      "evidence_chunk_ids":["<chunk_uuid>"]
    }
  ],
  "open_questions":["..."],
  "issues":[
    {
      "type":"missing_owner|missing_due_date|vague|contradiction|missing_context|other",
      "description":"...",
      "evidence_chunk_ids":["<chunk_uuid>"]
    }
  ],
  "had_retry": false,
  "invalid_reason_counts": {}
}
```

Errors:
- `404 {"detail":"meeting not found"}`

Special behavior:
- If no retrieved chunks and meeting is still indexing (and has no indexed chunks), returns a `missing_context` issue with summary:
  - `"This meeting is still being indexed. Try again in a moment."`

## 3.6 Internal Ops Endpoint

### `POST /internal/reaper/trigger?max_age_minutes=30`
Enqueues stale-processing cleanup job.

Header:
- `x-reaper-token: <token>` only required if `REAPER_TRIGGER_TOKEN` env is set.

Success `200`:
```json
{"queued": true, "job_id":"..."}
```

Errors:
- `401 {"detail":"invalid reaper token"}`
- `500 {"detail":"failed to enqueue reaper job: ..."}`

Frontend usually should not call this route; it is for scheduler/ops.

## 4) Indexing State Machine (Frontend UX)

Document status transitions:

1. `pending`:
   - set immediately on ingest/reindex request
   - job queued
2. `processing`:
   - worker started
   - `processing_started_at` set
3. terminal:
   - `indexed` on success (`indexed_at` set)
   - `failed` on error (`error` set)

Recommended frontend behavior:

- After upload: poll `GET /documents/{document_id}` every 2-5s.
- Enable chat/verify once at least one relevant doc is `indexed`.
- Show inline status chips:
  - pending/processing -> "Indexing..."
  - indexed -> "Ready"
  - failed -> "Failed" + `Reindex` button

## 5) Retrieval / Grounding Semantics (Important for UX)

Chat retrieval:
- meeting-scoped only
- only chunks where `embedding IS NOT NULL`
- cosine distance ordering
- top-k used by endpoint: `6`

Verify retrieval:
- meeting-scoped only
- only chunks with embeddings
- ordered by `chunk_index`
- capped at `40` chunks

This means:
- if indexing has not produced embeddings yet, chat/verify may return indexing/no-context messages.

## 6) Background Jobs (Operational Context)

Queue behavior in `app/queue.py`:

- `enqueue_index_document(document_id)`
  - job id dedup: `index-document:{document_id}`
  - timeout: `INDEX_JOB_TIMEOUT_SECONDS` (default `900`)
  - retries/backoff:
    - `INDEX_JOB_RETRY_MAX` (default `3`)
    - `INDEX_JOB_RETRY_INTERVALS` (default `30,120,300`)

- `enqueue_reaper_job(max_age_minutes)`
  - job id dedup: `reap-stale-processing-documents`

Worker entrypoint:
- `python -m app.worker`

## 7) Migrations / Schema Source of Truth

Alembic is authoritative:
- `20260222_0001_initial_schema` (baseline tables + pgvector extension)
- `20260222_0002_runs_response_json` (`runs.response_json`)

Apply migrations:
```bash
cd apps/api
./.venv/bin/alembic upgrade head
```

If DB existed before Alembic:
```bash
./.venv/bin/alembic stamp head
```

## 8) Known API Quirks / Gaps for Frontend Planning

1. No auth/session model yet.
2. No file upload endpoint yet (ingest is text payload only).

Design implication:
- frontend can build list-based screens now (`GET /meetings`, `GET /meetings/{meeting_id}/documents`).

## 9) Suggested Frontend Integration Flow

1. Create meeting
2. Upload/paste document text (ingest)
3. Poll document status until indexed
4. Enable:
   - Chat tab (`/chat`)
   - Verify tab (`/verify`)
5. If failed:
   - show error
   - allow reindex

## 10) Minimal Example Sequence

```bash
# 1) Create meeting
curl -s -X POST "http://127.0.0.1:8000/meetings?title=Demo"

# 2) Ingest text
curl -s -X POST "http://127.0.0.1:8000/meetings/<MEETING_ID>/documents" \
  -H "Content-Type: application/json" \
  -d '{"doc_type":"notes","filename":"m1.txt","text":"We decided to ship Friday and Alice owns QA."}'

# 3) Poll status
curl -s "http://127.0.0.1:8000/documents/<DOCUMENT_ID>"

# 4) Ask chat
curl -s -X POST "http://127.0.0.1:8000/meetings/<MEETING_ID>/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"What did we decide?"}'

# 5) Verify meeting
curl -s -X POST "http://127.0.0.1:8000/meetings/<MEETING_ID>/verify"
```
