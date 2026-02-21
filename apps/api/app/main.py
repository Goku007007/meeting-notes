from fastapi import FastAPI
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.db.session import engine
from app.db.models import Base, Meeting
from app.db.deps import get_db
import uuid


#chunking
from fastapi import HTTPException
from sqlalchemy import select
from app.db.models import Meeting, Document, Chunk
from app.schemas.documents import DocumentCreate, DocumentCreateResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.ingestion.chunking import chunk_text
from app.ai.embeddings import embed_texts
from app.ai.client import retrieve_similar_chunks, answer_with_citations

#apikey
from dotenv import load_dotenv

load_dotenv()


app = FastAPI()

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
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")

    query_vectors = await embed_texts([payload.question])
    if not query_vectors:
        raise HTTPException(status_code=500, detail="failed to embed question")

    chunks = await retrieve_similar_chunks(db, meeting_id, query_vectors[0], top_k=6)
    if not chunks:
        return ChatResponse(answer="I don't know based on the provided context.", citations=[])

    grounded = await answer_with_citations(payload.question, chunks)
    return ChatResponse(**grounded)
