from fastapi import Depends
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
import logging
import os
import time
import uuid

from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import CHAT_MODEL, answer_with_citations, retrieve_similar_chunks
from app.ai.embeddings import EMBEDDING_MODEL, embed_texts
from app.db.deps import get_db
from app.db.models import Chunk, Document, Meeting
from app.db.session import engine
from app.observability.runs import log_chat_run, log_verify_run
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
    return {"id": str(meeting.id), "title": meeting.title}


@app.get("/meetings", response_model=list[MeetingResponse])
async def list_meetings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Meeting).order_by(Meeting.created_at.desc()))
    meetings = result.scalars().all()
    return [{"id": str(meeting.id), "title": meeting.title} for meeting in meetings]


@app.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")
    return{"id": str(meeting.id),"title":meeting.title}



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


@app.post("/meetings/{meeting_id}/chat", response_model=ChatResponse)
async def chat_with_meeting(meeting_id: uuid.UUID, payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Capture total request latency for observability.
    t0 = time.monotonic()

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")

    query_vectors = await embed_texts([payload.question])
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

    grounded, meta = await answer_with_citations(payload.question, chunks)
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

    # Step 6.3: run extraction + grounding + rule checks.
    verify_response, meta = await verify_meeting(db=db, meeting_id=meeting_id)
    if (
        not meta.get("retrieved_chunk_ids")
        and await _meeting_indexing_in_progress(db, meeting_id)
        and not await _meeting_has_indexed_chunks(db, meeting_id)
    ):
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
