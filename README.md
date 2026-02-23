# meeting-notes

Meeting intelligence app with a FastAPI backend + Next.js frontend.

Current capabilities:
- Meeting creation and listing
- File upload ingestion (single or multi-file)
- Background extraction + chunking + embeddings (RQ worker)
- Retrieval-augmented chat (RAG) with citation guardrails
- Verify pipeline (decisions, actions, issues)
- Run-level observability for chat/verify
- ChatGPT-style frontend shell with meetings rail, chat composer, and artifacts rail

## Repository Layout

```text
meeting-notes/
  apps/
    api/
      app/
        ai/                  # embeddings, chat grounding/citation logic
        db/                  # SQLAlchemy models/session/deps
        ingestion/           # text chunking
        jobs/                # indexing + stale processing reaper
        observability/       # run logging helpers
        processing/          # file type validation + extraction
        schemas/             # API request/response models
        verifier/            # verify engine
        main.py              # API routes + orchestration
        queue.py             # RQ enqueue helpers
        worker.py            # worker entrypoint
      alembic/
      tests/
    web/
      src/
        app/                 # Next App Router + route-group shell
        components/          # chat/docs/verify/shell components
        lib/                 # api client, query hooks, derived state
  backendap.md               # backend contract for frontend/agents
  frontend-plan.md           # frontend architecture + UX plan
```

## Backend Highlights

- Queue-backed indexing path:
  - `POST /meetings/{meeting_id}/documents` (text ingest)
  - `POST /meetings/{meeting_id}/documents/upload` (multipart file ingest)
- Supported file types at upload validation:
  - PDF, DOCX, PPTX, XLSX, HTML, EML, TXT/MD, PNG/JPG/WEBP
- Upload guardrails:
  - MIME/extension allowlist
  - max upload size (`MAX_UPLOAD_BYTES`, default 25 MB)
- Worker processing:
  - extraction timeout (`EXTRACTION_TIMEOUT_SECONDS`)
  - max extracted text cap (`MAX_EXTRACTED_TEXT_CHARS`)
  - write new chunks first, clean previous chunks after commit
- Chat guardrails:
  - citations validated against retrieved chunks
  - retry once with stricter constraints
  - safe handling when citations are invalid
- Verify guardrails:
  - strict JSON schema output
  - evidence validation + deterministic issue rules

## Frontend Highlights

- Desktop: 3-column app shell
  - left rail: meetings + create
  - center: chat thread + composer + attachments
  - right rail: verify/tasks/issues/docs
- Mobile:
  - meetings drawer + workspace tabs
- Polling:
  - poll meeting docs list while any doc is pending/processing
- UX polish:
  - loading states and transitions
  - chat history persisted per meeting in browser localStorage

## Local Development

## 1) Start infra

```bash
cd meeting-notes
docker compose up -d db redis
```

## 2) Backend setup

```bash
cd apps/api
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
set -a
source .env
set +a
./.venv/bin/alembic upgrade head
```

If your DB already had tables before Alembic:

```bash
./.venv/bin/alembic stamp head
```

## 3) Run backend API

```bash
cd apps/api
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 4) Run worker (separate terminal)

```bash
cd apps/api
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
set -a
source .env
set +a
PYTHONPATH=. ./.venv/bin/rq worker default --url redis://localhost:6379/0 --with-scheduler
```

## 5) Frontend setup + run

```bash
cd apps/web
npm install
npm run dev -- --port 3010
```

Open:
- Frontend: `http://localhost:3010`
- Backend docs: `http://127.0.0.1:8000/docs`

## End-to-End Smoke Check

```bash
API=http://127.0.0.1:8000
MEETING_ID=$(curl -s -X POST "$API/meetings?title=Smoke" | jq -r '.id')

curl -s -X POST "$API/meetings/$MEETING_ID/documents/upload" \
  -F 'doc_type=notes' \
  -F 'files=@/absolute/path/to/sample-upload.md'

curl -s "$API/meetings/$MEETING_ID/documents"

curl -s -X POST "$API/meetings/$MEETING_ID/chat" \
  -H 'Content-Type: application/json' \
  -d '{"question":"What did we decide?"}'

curl -s -X POST "$API/meetings/$MEETING_ID/verify"
```

## Documentation Map

- Backend contract: `backendap.md`
- Frontend architecture/UX plan: `frontend-plan.md`
- Alembic usage: `apps/api/alembic/README.md`
- Web app local run: `apps/web/README.md`

## Notes

- Auth is not implemented yet (demo/local mode).
- Chat may return answers with no citations when citation quotes fail strict validation.
- CORS is configured for localhost/127.0.0.1 dev origins (port-flexible).
