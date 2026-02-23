from fastapi import Depends
from fastapi import File
from fastapi import FastAPI
from fastapi import Form
from fastapi import Header
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from pathlib import Path
import time
import uuid

from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import CHAT_MODEL, answer_with_citations, retrieve_similar_chunks
from app.ai.embeddings import EMBEDDING_MODEL, embed_texts
from app.db.deps import get_db
from app.db.models import Chunk, Document, Meeting, Run
from app.db.session import engine
from app.observability.runs import log_chat_run, log_verify_run
from app.processing import UnsupportedFormatError, validate_supported_upload
from app.schemas.documents import (
    DocumentCreate,
    DocumentCreateResponse,
    DocumentListItemResponse,
    DocumentStatusResponse,
)
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.meetings import MeetingResponse
from app.queue import enqueue_index_document, enqueue_reaper_job
from app.schemas.verify import Issue, VerifyResponse
from app.verifier.engine import verify_meeting

load_dotenv()


app = FastAPI()
logger = logging.getLogger(__name__)
DEBUG_GROUNDING = os.getenv("DEBUG_GROUNDING", "false").strip().lower() in {"1", "true", "yes", "on"}
UPLOADS_ROOT = Path(
    os.getenv("UPLOADS_DIR", str(Path(__file__).resolve().parents[3] / "uploads"))
)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]
# Default local-dev safety net: allow localhost/127.0.0.1 on any port.
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)

# Allow the local frontend app to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # (optional safety) ensures pgvector extension exists
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Alembic is the only schema manager in runtime environments.

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "API is running try /health or /docs"}

@app.post("/meetings")
async def create_meeting(title: str, db: AsyncSession = Depends(get_db)):
    meeting = Meeting(title = title)
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting) #pulls generated fields like id back from DB
    return {"id": str(meeting.id), "title": meeting.title, "created_at": meeting.created_at}


@app.get("/meetings", response_model=list[MeetingResponse])
async def list_meetings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Meeting).order_by(Meeting.created_at.desc()))
    meetings = result.scalars().all()
    return [
        {"id": str(meeting.id), "title": meeting.title, "created_at": meeting.created_at}
        for meeting in meetings
    ]


@app.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")
    return {"id": str(meeting.id), "title": meeting.title, "created_at": meeting.created_at}



#chunking

@app.post("/meetings/{meeting_id}/documents", response_model=DocumentCreateResponse)
async def create_document(meeting_id: uuid.UUID, payload: DocumentCreate, db: AsyncSession = Depends(get_db)):
    # 1) Validate the meeting exists (otherwise we'd create orphan documents)
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")

    # 2) Create the document row
    doc = Document(
        meeting_id=meeting_id,
        doc_type=payload.doc_type,
        filename=payload.filename,
        raw_text=payload.text,
        status="pending",
        error=None,
        processing_started_at=None,
        indexed_at=None,
    )
    db.add(doc)

    try:
        # Persist first so the queued job has a stable, committed document ID.
        await db.commit()
        await db.refresh(doc)

        try:
            enqueue_index_document(str(doc.id))
        except Exception as queue_exc:
            doc.status = "failed"
            doc.error = f"queue failed: {queue_exc}"[:4000]
            await db.commit()
            raise HTTPException(status_code=500, detail="failed to enqueue indexing job")

        return DocumentCreateResponse(document_id=str(doc.id), status=doc.status)
    except Exception:
        await db.rollback()
        raise


@app.post(
    "/meetings/{meeting_id}/documents/upload",
    response_model=DocumentCreateResponse | list[DocumentCreateResponse],
)
async def upload_document(
    meeting_id: uuid.UUID,
    doc_type: str = Form(...),
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    filename: str | None = Form(default=None),
    upload_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> DocumentCreateResponse | list[DocumentCreateResponse]:
    """
    Multipart upload endpoint (file-in pipeline).
    Stores the raw file, creates a pending Document row, then enqueues background processing.
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")

    normalized_doc_type = doc_type.strip()
    if not normalized_doc_type:
        raise HTTPException(status_code=400, detail="doc_type is required")
    if len(normalized_doc_type) > 50:
        raise HTTPException(status_code=400, detail="doc_type must be 50 characters or less")

    upload_files: list[UploadFile] = []
    if file is not None:
        upload_files.append(file)
    if files:
        upload_files.extend(files)
    if not upload_files:
        raise HTTPException(status_code=400, detail="at least one file is required")

    responses: list[DocumentCreateResponse] = []
    for current_file in upload_files:
        try:
            # Enforce a strict file-type allowlist at the edge.
            validate_supported_upload(current_file.filename, current_file.content_type)
        except UnsupportedFormatError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc

        content = await current_file.read()
        await current_file.close()
        if not content:
            raise HTTPException(status_code=400, detail="uploaded file is empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"file too large; max allowed is {MAX_UPLOAD_BYTES} bytes",
            )

        document_id = uuid.uuid4()
        original_filename = Path(current_file.filename or "upload.bin").name
        normalized_filename = Path(filename).name if filename else original_filename
        mime_type = (current_file.content_type or "").strip() or None
        size_bytes = len(content)

        doc_dir = UPLOADS_ROOT / str(document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        storage_path = doc_dir / original_filename
        storage_path.write_bytes(content)

        doc = Document(
            id=document_id,
            meeting_id=meeting_id,
            doc_type=normalized_doc_type,
            filename=normalized_filename,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=str(storage_path),
            raw_text="",
            status="pending",
            error=None,
            processing_started_at=None,
            indexed_at=None,
        )
        db.add(doc)

        try:
            await db.commit()
            await db.refresh(doc)

            try:
                enqueue_index_document(str(doc.id))
            except Exception as queue_exc:
                doc.status = "failed"
                doc.error = f"queue failed: {queue_exc}"[:4000]
                await db.commit()
                raise HTTPException(status_code=500, detail="failed to enqueue indexing job")

            responses.append(
                DocumentCreateResponse(
                    document_id=str(doc.id),
                    status=doc.status,
                    original_filename=original_filename,
                    upload_id=upload_id,
                )
            )
        except Exception:
            await db.rollback()
            try:
                if storage_path.exists():
                    storage_path.unlink()
                if doc_dir.exists() and not any(doc_dir.iterdir()):
                    doc_dir.rmdir()
            except Exception:
                logger.exception("failed to clean up uploaded file after create failure")
            raise

    if len(responses) == 1:
        return responses[0]
    return responses


@app.get("/meetings/{meeting_id}/documents", response_model=list[DocumentListItemResponse])
async def list_meeting_documents(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")

    docs_result = await db.execute(
        select(Document).where(Document.meeting_id == meeting_id).order_by(Document.created_at.desc())
    )
    docs = docs_result.scalars().all()
    return [
        DocumentListItemResponse(
            document_id=str(doc.id),
            meeting_id=str(doc.meeting_id),
            doc_type=doc.doc_type,
            filename=doc.filename,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            status=doc.status,
            error=doc.error,
            processing_started_at=doc.processing_started_at,
            indexed_at=doc.indexed_at,
        )
        for doc in docs
    ]


@app.post("/internal/reaper/trigger")
async def trigger_reaper(
    max_age_minutes: int | None = None,
    x_reaper_token: str | None = Header(default=None),
):
    """
    Small operational endpoint for scheduled cleanup.
    Protect with REAPER_TRIGGER_TOKEN in production.
    """
    required_token = os.getenv("REAPER_TRIGGER_TOKEN")
    if required_token and x_reaper_token != required_token:
        raise HTTPException(status_code=401, detail="invalid reaper token")

    try:
        job_id = enqueue_reaper_job(max_age_minutes=max_age_minutes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to enqueue reaper job: {exc}") from exc

    return {"queued": True, "job_id": job_id}


@app.get("/documents/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return DocumentStatusResponse(
        document_id=str(doc.id),
        status=doc.status,
        filename=doc.filename,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        error=doc.error,
        processing_started_at=doc.processing_started_at,
        indexed_at=doc.indexed_at,
    )


@app.post("/documents/{document_id}/reindex", response_model=DocumentCreateResponse)
async def reindex_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Re-enqueue indexing for an existing document.
    Useful for failed jobs or explicit reprocessing requests.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="document is already processing")

    doc.status = "pending"
    doc.error = None
    doc.processing_started_at = None
    doc.indexed_at = None
    await db.commit()
    await db.refresh(doc)

    try:
        enqueue_index_document(str(doc.id))
    except Exception as queue_exc:
        doc.status = "failed"
        doc.error = f"queue failed: {queue_exc}"[:4000]
        await db.commit()
        raise HTTPException(status_code=500, detail="failed to enqueue indexing job")

    return DocumentCreateResponse(document_id=str(doc.id), status=doc.status)


async def _meeting_indexing_in_progress(db: AsyncSession, meeting_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(Document.id)
        .where(Document.meeting_id == meeting_id)
        .where(Document.status.in_(["pending", "processing"]))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _meeting_has_indexed_chunks(db: AsyncSession, meeting_id: uuid.UUID) -> bool:
    """
    True when at least one chunk for the meeting is already indexed.
    We use this to avoid showing "still indexing" when there is already
    searchable content and the user question is simply unsupported.
    """
    result = await db.execute(
        select(Chunk.id)
        .where(Chunk.meeting_id == meeting_id)
        .where(Chunk.embedding.is_not(None))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _load_recent_chat_turns(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    limit: int = 6,
) -> list[tuple[str, str | None]]:
    """
    Load recent chat runs (oldest -> newest) for lightweight conversational continuity.
    Each tuple is (user_question, assistant_answer_or_none).
    """
    result = await db.execute(
        select(Run)
        .where(Run.meeting_id == meeting_id)
        .where(Run.run_type == "chat")
        .order_by(Run.created_at.desc())
        .limit(limit)
    )
    runs = list(reversed(result.scalars().all()))
    turns: list[tuple[str, str | None]] = []
    for run in runs:
        user_question = (run.input_text or "").strip()
        if not user_question:
            continue
        assistant_answer: str | None = None
        if isinstance(run.response_json, dict):
            value = run.response_json.get("answer")
            if isinstance(value, str) and value.strip():
                assistant_answer = value.strip()
        turns.append((user_question, assistant_answer))
    return turns


def _format_history_for_chat_prompt(turns: list[tuple[str, str | None]]) -> str:
    lines: list[str] = []
    for user_question, assistant_answer in turns:
        lines.append(f"User: {user_question}")
        if assistant_answer:
            lines.append(f"Assistant: {assistant_answer}")
    return "\n".join(lines)


@app.post("/meetings/{meeting_id}/chat", response_model=ChatResponse)
async def chat_with_meeting(meeting_id: uuid.UUID, payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Capture total request latency for observability.
    t0 = time.monotonic()

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")

    recent_turns = await _load_recent_chat_turns(db=db, meeting_id=meeting_id, limit=6)

    # Improve follow-up questions ("what about that?") by enriching retrieval query
    # with a small amount of recent user context.
    recent_user_questions = [q for q, _ in recent_turns[-2:]]
    retrieval_question = payload.question
    if recent_user_questions:
        retrieval_question = "\n".join([*recent_user_questions, payload.question])

    query_vectors = await embed_texts([retrieval_question])
    if not query_vectors:
        raise HTTPException(status_code=500, detail="failed to embed question")

    # Retrieve relevant context chunks before generation.
    chunks = await retrieve_similar_chunks(db, meeting_id, query_vectors[0], top_k=6)
    retrieved_chunk_ids = [str(chunk.id) for chunk in chunks]
    if DEBUG_GROUNDING:
        logger.info("grounding.retrieved_chunks meeting_id=%s count=%d", meeting_id, len(chunks))
    if not chunks:
        indexing_in_progress = await _meeting_indexing_in_progress(db, meeting_id)
        has_indexed_chunks = await _meeting_has_indexed_chunks(db, meeting_id)

        # Only say "still indexing" when *no* indexed content exists yet.
        if indexing_in_progress and not has_indexed_chunks:
            response = ChatResponse(
                answer="This meeting is still being indexed. Try again in a moment.",
                citations=[],
            )
        else:
            response = ChatResponse(answer="I don't know based on the provided context.", citations=[])
        try:
            # Best-effort run logging: failures must not break user-facing responses.
            await log_chat_run(
                db=db,
                meeting_id=meeting_id,
                question=payload.question,
                retrieved_chunk_ids=retrieved_chunk_ids,
                citations=response.model_dump()["citations"],
                response_payload=response.model_dump(),
                had_retry=False,
                invalid_reason_counts={},
                latency_ms=int((time.monotonic() - t0) * 1000),
                model=CHAT_MODEL,
                embedding_model=EMBEDDING_MODEL,
            )
        except Exception:
            logger.exception("failed to log chat run")
        return response

    history_text = _format_history_for_chat_prompt(recent_turns)
    model_question = payload.question
    if history_text:
        model_question = (
            "Use prior turns only when relevant for disambiguation.\n\n"
            f"CHAT HISTORY (oldest to newest):\n{history_text}\n\n"
            f"CURRENT QUESTION:\n{payload.question}"
        )

    grounded, meta = await answer_with_citations(model_question, chunks)
    response = ChatResponse(**grounded)

    try:
        # Persist a run row for debugging/audit: retrieval, citations, retry metadata, latency.
        await log_chat_run(
            db=db,
            meeting_id=meeting_id,
            question=payload.question,
            retrieved_chunk_ids=retrieved_chunk_ids,
            citations=response.model_dump()["citations"],
            response_payload=response.model_dump(),
            had_retry=bool(meta.get("had_retry", False)),
            invalid_reason_counts=dict(meta.get("invalid_reason_counts", {})),
            latency_ms=int((time.monotonic() - t0) * 1000),
            model=CHAT_MODEL,
            embedding_model=EMBEDDING_MODEL,
        )
    except Exception:
        logger.exception("failed to log chat run")

    return response


@app.post("/meetings/{meeting_id}/verify", response_model=VerifyResponse)
async def verify_endpoint(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # Step 6.3: endpoint wrapper around verifier engine so frontend can use the feature.
    t0 = time.monotonic()

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")

    # Short-circuit when meeting content is not ready yet to avoid unnecessary model calls.
    indexing_in_progress = await _meeting_indexing_in_progress(db, meeting_id)
    has_indexed_chunks = await _meeting_has_indexed_chunks(db, meeting_id)
    if indexing_in_progress and not has_indexed_chunks:
        verify_response = VerifyResponse(
            structured_summary="This meeting is still being indexed. Try again in a moment.",
            decisions=[],
            action_items=[],
            open_questions=[],
            issues=[
                Issue(
                    type="missing_context",
                    description="Meeting indexing is still in progress.",
                    evidence_chunk_ids=[],
                )
            ],
            had_retry=False,
            invalid_reason_counts={},
        )
        meta = {
            "had_retry": False,
            "invalid_reason_counts": {},
            "retrieved_chunk_ids": [],
            "model": "gpt-4.1-mini",
        }
    elif not has_indexed_chunks:
        verify_response = VerifyResponse(
            structured_summary="No indexed meeting content is available to verify.",
            decisions=[],
            action_items=[],
            open_questions=[],
            issues=[
                Issue(
                    type="missing_context",
                    description="No indexed chunks found for this meeting.",
                    evidence_chunk_ids=[],
                )
            ],
            had_retry=False,
            invalid_reason_counts={},
        )
        meta = {
            "had_retry": False,
            "invalid_reason_counts": {},
            "retrieved_chunk_ids": [],
            "model": "gpt-4.1-mini",
        }
    else:
        try:
            # Step 6.3: run extraction + grounding + rule checks.
            verify_response, meta = await verify_meeting(db=db, meeting_id=meeting_id)
        except Exception:
            # Fail-safe behavior: verification errors should not surface as raw 500s.
            logger.exception("verify engine failed meeting_id=%s", meeting_id)
            verify_response = VerifyResponse(
                structured_summary="Unable to verify this meeting right now. Please try again.",
                decisions=[],
                action_items=[],
                open_questions=[],
                issues=[
                    Issue(
                        type="other",
                        description="Verifier engine failed unexpectedly.",
                        evidence_chunk_ids=[],
                    )
                ],
                had_retry=False,
                invalid_reason_counts={},
            )
            meta = {
                "had_retry": False,
                "invalid_reason_counts": {},
                "retrieved_chunk_ids": [],
                "model": "gpt-4.1-mini",
            }

    try:
        # Step 6.3: best-effort run logging (endpoint response should not fail if logging fails).
        await log_verify_run(
            db=db,
            meeting_id=meeting_id,
            retrieved_chunk_ids=list(meta.get("retrieved_chunk_ids", [])),
            verify_payload=verify_response.model_dump(),
            had_retry=bool(meta.get("had_retry", False)),
            invalid_reason_counts=dict(meta.get("invalid_reason_counts", {})),
            latency_ms=int((time.monotonic() - t0) * 1000),
            model=str(meta.get("model", "gpt-4.1-mini")),
        )
    except Exception:
        logger.exception("failed to log verify run")

    return verify_response
