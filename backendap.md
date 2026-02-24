# Backend API Contract for Frontend and Agent Design

Source of truth for backend behavior.

Primary code references:
- `apps/api/app/main.py`
- `apps/api/app/schemas/*.py`
- `apps/api/app/db/models.py`
- `apps/api/app/jobs/indexing.py`
- `apps/api/app/ai/client.py`
- `apps/api/app/verifier/engine.py`

## 1) Global Contract

- Base URL (local): `http://127.0.0.1:8000`
- OpenAPI docs: `GET /docs`
- IDs: UUID strings
- Error format: FastAPI style `{"detail":"..."}`
- CORS: controlled by env (`CORS_ALLOW_ORIGINS`, `CORS_ALLOW_ORIGIN_REGEX`)
  - in `staging/production`, wildcard origins/regex are rejected at startup

Auth model (Guest Mode):
- `POST /sessions/guest` returns a bearer token and may also set an `httpOnly` cookie when enabled.
- Frontend may authenticate using `Authorization: Bearer <token>` and/or cookie transport.
- Data access is session-scoped (meeting ownership enforced server-side).
- Session TTL enforcement:
  - idle timeout via `GUEST_SESSION_IDLE_TTL_HOURS`
  - max session age via `GUEST_SESSION_MAX_AGE_HOURS`
  - expired sessions are rejected and cleaned up.
- Session management:
  - `POST /sessions/reset` rotates session
  - `DELETE /sessions/current` invalidates session + owned data
- Cookie auth safety:
  - optional cookie transport (`GUEST_SESSION_COOKIE_ENABLED=true`)
  - mutating cookie-auth requests require CSRF header (`x-csrf-token`) matching CSRF cookie

## 2) Core Objects

### 2.1 Meeting

```json
{
  "id": "<uuid>",
  "title": "Planning",
  "created_at": "2026-02-23T08:00:00Z"
}
```

### 2.2 Document

```json
{
  "document_id": "<uuid>",
  "meeting_id": "<uuid>",
  "doc_type": "notes",
  "filename": "notes.md",
  "original_filename": "notes.md",
  "mime_type": "text/markdown",
  "size_bytes": 1024,
  "status": "pending|processing|indexed|failed",
  "error": null,
  "processing_started_at": null,
  "indexed_at": null
}
```

### 2.3 Chunk

```json
{
  "id": "<uuid>",
  "meeting_id": "<uuid>",
  "document_id": "<uuid>",
  "chunk_index": 0,
  "text": "...",
  "embedding": "vector(1536)"
}
```

### 2.4 Run (observability)

```json
{
  "id": "<uuid>",
  "meeting_id": "<uuid>",
  "run_type": "chat|verify",
  "input_text": "...",
  "retrieved_chunk_ids": ["<uuid>"],
  "response_citations": [],
  "response_json": {},
  "had_retry": false,
  "invalid_citation_reasons": {},
  "latency_ms": 1234,
  "model": "gpt-4.1-mini",
  "embedding_model": "text-embedding-3-small"
}
```

### 2.5 Guest Session

```json
{
  "session_id": "<uuid>",
  "token": "<bearer_token>",
  "created_at": "...",
  "expires_at": "..."
}
```

## 3) Endpoints

## 3.1 Health

### `GET /health`

`200`

```json
{"ok": true}
```

### `GET /health/ready`

Checks DB + Redis queue connectivity.

`200` when ready, `503` when any required dependency is down.

### `GET /health/worker`

Returns worker visibility via RQ worker registry.

```json
{"ok": true, "worker_count": 1}
```

### `GET /`

`200`

```json
{"message":"API is running try /health or /docs"}
```

## 3.2 Sessions

### `POST /sessions/guest`

Creates anonymous guest session token.
Rate limited by IP (`RATE_LIMIT_SESSION_CREATE_PER_MINUTE_IP`).
Also triggers cleanup of expired guest sessions.

`200`

```json
{"token":"...","session_id":"<uuid>","created_at":"...","expires_at":"..."}
```

### `POST /sessions/reset`

Invalidates current session (if present), creates a new guest session, and returns a fresh token.

`200`

```json
{"token":"...","session_id":"<uuid>","created_at":"...","expires_at":"..."}
```

### `DELETE /sessions/current`

Invalidates current guest session and deletes its owned data.

`200`

```json
{"ok": true}
```

CSRF note:
- if using cookie auth without `Authorization: Bearer`, mutating routes require:
  - cookie `CSRF_COOKIE_NAME`
  - header `x-csrf-token` with same value

## 3.3 Meetings (Authorization required)

### `POST /meetings?title=<title>`

`200`

```json
{"id":"<uuid>","title":"<title>","created_at":"..."}
```

### `GET /meetings`

Returns meetings owned by current guest session only.

### `GET /meetings/{meeting_id}`

Returns meeting only if owned by current session.

## 3.4 Documents (Authorization required)

### `POST /meetings/{meeting_id}/documents`

Text ingestion endpoint.

### `POST /meetings/{meeting_id}/documents/upload`

Multipart ingestion (single or multiple files).

Accepted types:
- PDF, DOCX, PPTX, XLSX, HTML/HTM, EML, TXT/MD, PNG/JPG/JPEG/WEBP
- Max files per request: `MAX_FILES_PER_UPLOAD_REQUEST` (default `10`, returns `413` when exceeded)

Response:
- single file: object
- multi file: array of objects

```json
{"document_id":"<uuid>","status":"pending","original_filename":"a.md","upload_id":"batch-1"}
```

### `GET /meetings/{meeting_id}/documents`

Lists documents for owned meeting.

### `GET /documents/{document_id}`

Returns document status if document belongs to owned meeting.

### `POST /documents/{document_id}/reindex`

Re-enqueues indexing for owned document.
Protected by cooldown (`REINDEX_COOLDOWN_SECONDS`) and queue fairness caps.

## 3.5 Chat (Authorization required)

### `POST /meetings/{meeting_id}/chat`

Request:

```json
{"question":"What did we decide?"}
```

Response:

```json
{
  "answer":"...",
  "citations":[{"chunk_id":"<uuid>","quote":"..."}],
  "run_id":"<uuid>"
}
```

Behavior:
- Retrieval is meeting-scoped, top-k=6, embeddings-only chunks.
- Recent chat turns are used for follow-up disambiguation.
- Citations are generated deterministically server-side from retrieved chunks.
- If no usable context exists: safe fallback answer and empty citations.

### `GET /meetings/{meeting_id}/chat/history?limit=100`

Returns DB-backed chat history for owned meeting.

```json
[
  {
    "run_id":"<uuid>",
    "question":"...",
    "answer":"...",
    "citations":[{"chunk_id":"<uuid>","quote":"..."}],
    "created_at":"..."
  }
]
```

### `POST /meetings/{meeting_id}/chat/feedback`

Telemetry for answer quality.

Request:

```json
{"run_id":"<uuid>","verdict":"up|down","reason":"optional"}
```

## 3.6 Verify (Authorization required)

### `POST /meetings/{meeting_id}/verify`

Returns structured summary/decisions/action items/issues.

Behavior:
- Safe fallback response on internal verifier failure (no raw 500 leak).
- Indexing-aware `missing_context` handling.

## 3.7 Evidence/Chunks (Authorization required)

### `GET /chunks/{chunk_id}`

Returns chunk text + linked document metadata for evidence drawers/debug trust.

## 3.8 Internal Ops

### `POST /internal/reaper/trigger?max_age_minutes=30`

Optional header when token configured:
- `x-reaper-token: <token>`
- `x-admin-token: <ADMIN_API_TOKEN>` required

## 3.9 Analytics

### `GET /analytics/answer-quality`
### `GET /analytics/answer-quality?meeting_id=<uuid>`

Returns aggregated chat quality telemetry (admin only):
- total runs
- avg latency
- no-citation rate
- feedback verdict counts

Required header:
- `x-admin-token: <ADMIN_API_TOKEN>`

## 4) Rate Limits and Quotas

Per-IP and per-session per-minute limits are enforced for:
- session create (IP only)
- upload
- reindex
- chat
- verify

Daily session quotas are enforced for:
- uploads/day
- upload MB/day
- chats/day
- verifies/day

All limits are env-driven (`RATE_LIMIT_*`, `QUOTA_*`).

Additional controls:
- `MAX_ACTIVE_INDEX_JOBS_PER_SESSION` blocks one session from flooding queue.
- `REINDEX_COOLDOWN_SECONDS` prevents rapid reindex loops.

429 response shape (rate/quota/cooldown):
```json
{
  "detail": {
    "code": "rate_limited|reindex_cooldown",
    "message": "...",
    "retry_after_seconds": 30
  }
}
```

JSON request size guard:
- `MAX_JSON_BODY_BYTES` returns `413` for oversized JSON request bodies.

## 4.1 Security Headers

API responses include:
- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`

## 5) Indexing State Machine

Document states:
1. `pending`
2. `processing`
3. terminal: `indexed` | `failed`

Frontend recommendation:
- Poll `GET /meetings/{meeting_id}/documents` every 2s while any document is pending/processing.

## 6) Extraction, OCR, and Storage

Worker behavior:
- Extracts text from file or OCR fallback (when `ENABLE_OCR=true` and OCR deps installed).
- Chunks and embeds text.
- Marks document `indexed` or `failed`.
- Hard caps:
  - `MAX_EXTRACTED_TEXT_CHARS`
  - `MAX_CHUNKS_PER_DOCUMENT`
  - `EXTRACTION_TIMEOUT_SECONDS`
  - `OCR_TIMEOUT_SECONDS`
  - `PDF_MAX_PAGES`
- HTML/email extraction sanitizes script/style/noscript content before text extraction.
- Malware scanning is not built-in by default; rely on strict allowlist + size/count caps unless AV is added.

Storage abstraction:
- `STORAGE_BACKEND=local` (dev)
- `STORAGE_BACKEND=s3` (prod)

Required for S3:
- `S3_BUCKET`
- optional `S3_PREFIX`

## 7) Queue and Worker

Queue behavior (`app/queue.py`):
- index enqueue: `enqueue_index_document(document_id)`
- reaper enqueue: `enqueue_reaper_job(max_age_minutes)`

Worker command:

```bash
cd apps/api
./scripts/run_worker_local.sh
```

Notes:
- On macOS, the script defaults to `rq.worker.SimpleWorker` to avoid Objective-C fork crashes.
- To force normal forking behavior: `RQ_WORKER_CLASS=rq.worker.Worker ./scripts/run_worker_local.sh`

## 8) Migrations

Current revisions:
- `20260222_0001_initial_schema`
- `20260222_0002_runs_response_json`
- `20260223_0003_documents_file_metadata`
- `20260223_0004_guest_sessions_and_feedback`

Apply:

```bash
cd apps/api
./.venv/bin/alembic upgrade head
```

## 9) Minimal cURL Sequence (Guest Mode)

```bash
API=http://127.0.0.1:8000
TOKEN=$(curl -s -X POST "$API/sessions/guest" | jq -r '.token')
AUTH="Authorization: Bearer $TOKEN"

MEETING_ID=$(curl -s -X POST "$API/meetings?title=Demo" -H "$AUTH" | jq -r '.id')

curl -s -X POST "$API/meetings/$MEETING_ID/documents/upload" \
  -H "$AUTH" \
  -F "doc_type=notes" \
  -F "files=@/absolute/path/to/sample-upload.md"

curl -s "$API/meetings/$MEETING_ID/documents" -H "$AUTH"

curl -s -X POST "$API/meetings/$MEETING_ID/chat" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"question":"What did we decide?"}'

curl -s "$API/meetings/$MEETING_ID/chat/history" -H "$AUTH"

curl -s -X POST "$API/meetings/$MEETING_ID/verify" -H "$AUTH"
```
