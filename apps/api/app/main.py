from fastapi import Depends
from fastapi import FastAPI
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
from app.db.models import Base, Chunk, Document, Meeting
from app.db.session import engine
from app.ingestion.chunking import chunk_text
from app.observability.runs import log_chat_run, log_verify_run
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.documents import DocumentCreate, DocumentCreateResponse
from app.schemas.verify import VerifyResponse
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
        await conn.run_sync(Base.metadata.create_all)

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

@app.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        return {"error": "not found"}
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
    )
    db.add(doc)

    try:
        # flush = "send pending INSERT so doc.id is available" (but not final commit yet)
        await db.flush()

        # 3) Chunk the text
        pieces = chunk_text(payload.text)

        if not pieces:
            await db.commit()
            return DocumentCreateResponse(document_id=str(doc.id), chunks_created=0)

        # 4) Embed all chunk pieces in one batch
        vectors = await embed_texts(pieces)
        if len(vectors) != len(pieces):
            raise ValueError("embedding count does not match chunk count")

        # 5) Create chunk rows
        for i, piece in enumerate(pieces):
            db.add(
                Chunk(
                    meeting_id=meeting_id,
                    document_id=doc.id,
                    chunk_index=i,
                    text=piece,
                    embedding=vectors[i],
                )
            )

        # 6) Commit once (saves both doc + all chunks atomically)
        await db.commit()
        return DocumentCreateResponse(document_id=str(doc.id), chunks_created=len(pieces))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="failed to create document and embeddings")


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
        response = ChatResponse(answer="I don't know based on the provided context.", citations=[])
        try:
            # Best-effort run logging: failures must not break user-facing responses.
            await log_chat_run(
                db=db,
                meeting_id=meeting_id,
                question=payload.question,
                retrieved_chunk_ids=retrieved_chunk_ids,
                citations=response.model_dump()["citations"],
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
