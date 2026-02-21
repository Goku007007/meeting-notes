from fastapi import FastAPI
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.db.session import engine
from app.db.models import Base, Meeting
from app.db.deps import get_db
import uuid

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


