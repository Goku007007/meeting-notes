# Backend API Contract for Frontend and Agent Design

Source of truth for current backend behavior.

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
- Auth: none
- IDs: UUID strings
- Error format: FastAPI style `{"detail":"..."}`
- CORS (dev): localhost / 127.0.0.1 allowed by regex (port-flexible)

## 2) Core Objects

## 2.1 Meeting

```json
{
  "id": "<uuid>",
  "title": "Planning",
  "created_at": "2026-02-23T08:00:00Z"
}
```

## 2.2 Document

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

## 2.3 Chunk

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

## 2.4 Run (observability)

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

## 3) Endpoints

## 3.1 Health

### `GET /health`

`200`

```json
{"ok": true}
```

### `GET /`

`200`

```json
{"message":"API is running try /health or /docs"}
```

## 3.2 Meetings

### `POST /meetings?title=<title>`

Creates meeting.

`200`

```json
{"id":"<uuid>","title":"<title>","created_at":"2026-02-23T08:00:00Z"}
```

### `GET /meetings`

Newest first.

`200`

```json
[
  {"id":"<uuid>","title":"Meeting A","created_at":"..."},
  {"id":"<uuid>","title":"Meeting B","created_at":"..."}
]
```

### `GET /meetings/{meeting_id}`

`200`

```json
{"id":"<uuid>","title":"...","created_at":"..."}
```

`404`

```json
{"detail":"meeting not found"}
```

## 3.3 Documents

### `POST /meetings/{meeting_id}/documents`

Text ingestion endpoint.

Request body:

```json
{
  "doc_type": "notes",
  "filename": "m1.txt",
  "text": "raw text"
}
```

`200`

```json
{"document_id":"<uuid>","status":"pending"}
```

Errors:
- `404 {"detail":"meeting not found"}`
- `500 {"detail":"failed to enqueue indexing job"}`

### `POST /meetings/{meeting_id}/documents/upload`

Multipart file ingestion.

Form fields:
- `doc_type` (required)
- `file` (single) and/or `files` (multi)
- `filename` (optional override)
- `upload_id` (optional, echoed in response)

Success response is one item for single upload, or list for multi upload.

Single (`200`):

```json
{"document_id":"<uuid>","status":"pending","original_filename":"notes.md","upload_id":"batch-1"}
```

Multi (`200`):

```json
[
  {"document_id":"<uuid>","status":"pending","original_filename":"a.md","upload_id":"batch-1"},
  {"document_id":"<uuid>","status":"pending","original_filename":"b.txt","upload_id":"batch-1"}
]
```

Validation/guardrail errors:
- `400` no file, empty file, invalid doc_type
- `404` meeting not found
- `413` file too large (`MAX_UPLOAD_BYTES`, default 25MB)
- `415` unsupported extension/MIME or mismatch
- `500` queue enqueue failure

Supported upload formats:
- PDF, DOCX, PPTX, XLSX, HTML/HTM, EML, TXT/MD, PNG/JPG/JPEG/WEBP

### `GET /meetings/{meeting_id}/documents`

Newest first.

`200`

```json
[
  {
    "document_id":"<uuid>",
    "meeting_id":"<uuid>",
    "doc_type":"notes",
    "filename":"m1.txt",
    "original_filename":"m1.txt",
    "mime_type":"text/plain",
    "size_bytes":26,
    "status":"pending|processing|indexed|failed",
    "error":null,
    "processing_started_at":null,
    "indexed_at":null
  }
]
```

`404 {"detail":"meeting not found"}`

### `GET /documents/{document_id}`

`200`

```json
{
  "document_id":"<uuid>",
  "status":"pending|processing|indexed|failed",
  "filename":"...",
  "original_filename":"...",
  "mime_type":"...",
  "size_bytes":123,
  "error":null,
  "processing_started_at":null,
  "indexed_at":null
}
```

`404 {"detail":"document not found"}`

### `POST /documents/{document_id}/reindex`

`200`

```json
{"document_id":"<uuid>","status":"pending"}
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

Response (`200`):

```json
{
  "answer":"...",
  "citations":[
    {"chunk_id":"<uuid>","quote":"..."}
  ]
}
```

Errors:
- `404 {"detail":"meeting not found"}`
- `500 {"detail":"failed to embed question"}`

Chat behavior details:
- Retrieval is meeting-scoped, embeddings-only chunks, cosine distance, top-k=6.
- Recent chat turns are loaded and used for follow-up disambiguation.
- Citation pipeline:
  - validates chunk_id allowlist + quote constraints
  - retries once on invalid citations
  - strips unsafe citations
  - can return answer with fallback citations when quote format fails but chunk IDs are valid
- Indexing/no-context behavior:
  - If no chunks and meeting still indexing: indexing message
  - If no chunks and no indexing: `I don't know based on the provided context.`

## 3.5 Verify

### `POST /meetings/{meeting_id}/verify`

No request body.

`200`

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

Special handling:
- endpoint no longer leaks raw 500s from verify engine; returns safe structured fallback on internal verify failures.
- If indexing in progress and no indexed chunks, returns `missing_context` issue with indexing message.

## 3.6 Internal Ops

### `POST /internal/reaper/trigger?max_age_minutes=30`

Header:
- `x-reaper-token: <token>` if `REAPER_TRIGGER_TOKEN` configured.

`200`

```json
{"queued": true, "job_id":"..."}
```

Errors:
- `401 {"detail":"invalid reaper token"}`
- `500 {"detail":"failed to enqueue reaper job: ..."}`

## 4) Indexing State Machine

Document states:
1. `pending` (created + queued)
2. `processing` (worker started)
3. terminal:
   - `indexed`
   - `failed`

Recommended frontend handling:
- Poll `GET /meetings/{meeting_id}/documents` every 2s while any doc is pending/processing.
- Show `Indexing...` / `Ready` / `Failed` status badges.
- Keep chat/verify UX aware of partial indexing.

## 5) Extraction and Processing Behavior

Worker extraction pipeline:
- Reads uploaded file from `storage_path`
- Extracts text by format-specific extractor
- Chunks text
- Embeds chunks
- Writes new chunks and marks indexed
- Best-effort cleans old chunks after success

Guardrails:
- extraction timeout: `EXTRACTION_TIMEOUT_SECONDS` (default `120`)
- max extracted chars: `MAX_EXTRACTED_TEXT_CHARS` (default `2_000_000`)
- oversized upload rejected at API edge (`MAX_UPLOAD_BYTES`)

Image files:
- accepted at upload
- extraction fails without OCR (`No extractable text found (image uploaded, OCR is not enabled).`)

## 6) Queue and Worker

Queue behavior (`app/queue.py`):
- index enqueue: `enqueue_index_document(document_id)`
  - job id: `index-document-<document_id>`
  - timeout: `INDEX_JOB_TIMEOUT_SECONDS` (default `900`)
  - retries: `INDEX_JOB_RETRY_MAX` + `INDEX_JOB_RETRY_INTERVALS`
- reaper enqueue: `enqueue_reaper_job(max_age_minutes)`
  - job id: `reap-stale-processing-documents`

Worker command:

```bash
PYTHONPATH=. ./.venv/bin/rq worker default --url redis://localhost:6379/0 --with-scheduler
```

## 7) Migrations

Alembic is authoritative.

Current revisions:
- `20260222_0001_initial_schema`
- `20260222_0002_runs_response_json`
- `20260223_0003_documents_file_metadata`

Apply:

```bash
cd apps/api
./.venv/bin/alembic upgrade head
```

Stamp existing DB:

```bash
./.venv/bin/alembic stamp head
```

## 8) Frontend-Relevant Gaps

- No auth/session model yet
- No server-side chat history endpoint yet (history is currently local UI persistence)
- OCR not enabled for image extraction

## 9) Minimal cURL Sequence

```bash
API=http://127.0.0.1:8000
MEETING_ID=$(curl -s -X POST "$API/meetings?title=Demo" | jq -r '.id')

curl -s -X POST "$API/meetings/$MEETING_ID/documents/upload" \
  -F "doc_type=notes" \
  -F "files=@/absolute/path/to/sample-upload.md"

curl -s "$API/meetings/$MEETING_ID/documents"

curl -s -X POST "$API/meetings/$MEETING_ID/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"What did we decide?"}'

curl -s -X POST "$API/meetings/$MEETING_ID/verify"
```
