import unittest
import uuid

from fastapi import HTTPException
from sqlalchemy import text

from app.db.models import Base, Document, Meeting
from app.db.session import SessionLocal, engine
from app.main import get_meeting, list_meeting_documents, list_meetings


class MeetingEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await engine.dispose()
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("ALTER TABLE runs ADD COLUMN IF NOT EXISTS response_json JSONB;"))
        self.db = SessionLocal()

    async def asyncTearDown(self) -> None:
        await self.db.rollback()
        await self.db.close()
        await engine.dispose()

    async def test_list_meetings_returns_newest_first(self) -> None:
        older = Meeting(title=f"older-{uuid.uuid4()}")
        newer = Meeting(title=f"newer-{uuid.uuid4()}")
        self.db.add(older)
        await self.db.commit()
        self.db.add(newer)
        await self.db.commit()

        rows = await list_meetings(self.db)
        titles = [row["title"] for row in rows]
        self.assertIn(newer.title, titles)
        self.assertIn(older.title, titles)
        self.assertLess(titles.index(newer.title), titles.index(older.title))

    async def test_get_meeting_returns_404_when_missing(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await get_meeting(uuid.uuid4(), self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_list_meeting_documents_returns_documents(self) -> None:
        meeting = Meeting(title=f"docs-{uuid.uuid4()}")
        self.db.add(meeting)
        await self.db.flush()

        doc = Document(
            meeting_id=meeting.id,
            doc_type="notes",
            filename="d1.txt",
            raw_text="hello",
            status="pending",
        )
        self.db.add(doc)
        await self.db.commit()

        docs = await list_meeting_documents(meeting.id, self.db)
        self.assertEqual(len(docs), 1)
        row = docs[0]
        self.assertEqual(row.document_id, str(doc.id))
        self.assertEqual(row.meeting_id, str(meeting.id))
        self.assertEqual(row.doc_type, "notes")
        self.assertEqual(row.filename, "d1.txt")
        self.assertEqual(row.status, "pending")


if __name__ == "__main__":
    unittest.main()
