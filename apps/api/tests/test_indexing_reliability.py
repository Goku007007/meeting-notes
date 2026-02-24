import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select, text

from app.db.models import Base, Chunk, Document, GuestSession, Meeting
from app.db.session import SessionLocal, engine
from app.jobs.indexing import index_document_async, reap_stale_processing_documents_async
from app.main import reindex_document


class IndexingReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await engine.dispose()
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("ALTER TABLE runs ADD COLUMN IF NOT EXISTS response_json JSONB;"))
        self.db = SessionLocal()
        self.session = GuestSession(token=f"test-token-{uuid.uuid4()}")
        self.db.add(self.session)
        await self.db.commit()
        await self.db.refresh(self.session)
        self.request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))

    async def asyncTearDown(self) -> None:
        await self.db.rollback()
        await self.db.close()
        await engine.dispose()

    async def _create_document(self, status: str = "pending") -> Document:
        meeting = Meeting(title=f"reliability-{uuid.uuid4()}", session_id=self.session.id)
        self.db.add(meeting)
        await self.db.flush()

        doc = Document(
            meeting_id=meeting.id,
            doc_type="notes",
            filename="r.txt",
            raw_text="hello",
            status=status,
            error=None,
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def test_reindex_moves_failed_doc_to_pending_and_enqueues(self) -> None:
        doc = await self._create_document(status="failed")
        # Reindex now has cooldown protection based on created/indexed/processing timestamps.
        # Backdate created_at so this test validates enqueue behavior, not cooldown rejection.
        # DB column is TIMESTAMP WITHOUT TIME ZONE; use naive UTC datetime for compatibility.
        doc.created_at = datetime.utcnow() - timedelta(minutes=10)
        await self.db.commit()
        await self.db.refresh(doc)

        called: list[str] = []
        with patch("app.main.enqueue_index_document", lambda doc_id: called.append(doc_id) or "queued"):
            response = await reindex_document(doc.id, self.request, self.session, self.db)

        self.assertEqual(response.document_id, str(doc.id))
        self.assertEqual(response.status, "pending")
        self.assertEqual(called, [str(doc.id)])

        refreshed = await self.db.get(Document, doc.id)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "pending")
        self.assertIsNone(refreshed.error)

    async def test_reindex_rejects_processing_document(self) -> None:
        doc = await self._create_document(status="processing")

        with self.assertRaises(HTTPException) as ctx:
            await reindex_document(doc.id, self.request, self.session, self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_reaper_marks_stale_processing_documents_failed(self) -> None:
        doc = await self._create_document(status="processing")
        stale_started_at = datetime.now(timezone.utc) - timedelta(minutes=90)
        doc.processing_started_at = stale_started_at
        await self.db.commit()

        changed = await reap_stale_processing_documents_async(max_age_minutes=30)
        # Other stale rows may exist in the shared test DB; at least this doc must be reaped.
        self.assertGreaterEqual(changed, 1)

        # Re-open a session so we don't read a stale in-memory ORM instance.
        await self.db.close()
        self.db = SessionLocal()
        result = await self.db.execute(select(Document).where(Document.id == doc.id))
        refreshed = result.scalar_one()
        self.assertEqual(refreshed.status, "failed")
        self.assertIn("timed out", str(refreshed.error))
        self.assertIsNone(refreshed.processing_started_at)

    async def test_reindex_failure_keeps_previous_chunks_available(self) -> None:
        """
        Regression guard for downtime window:
        if embedding fails during reindex, old chunks must still be present.
        """
        doc = await self._create_document(status="indexed")
        old_chunk = Chunk(
            meeting_id=doc.meeting_id,
            document_id=doc.id,
            chunk_index=0,
            text="old indexed content",
            embedding=[0.0] * 1536,
        )
        self.db.add(old_chunk)
        await self.db.commit()

        async def _boom(_texts: list[str]) -> list[list[float]]:
            raise RuntimeError("embedding failed")

        with patch("app.jobs.indexing.embed_texts", _boom):
            with self.assertRaises(RuntimeError):
                await index_document_async(str(doc.id))

        await self.db.close()
        self.db = SessionLocal()

        # Old chunks should remain because delete now happens only after successful insert+commit.
        result = await self.db.execute(select(Chunk).where(Chunk.document_id == doc.id))
        remaining = list(result.scalars().all())
        self.assertGreaterEqual(len(remaining), 1)

        refreshed = await self.db.get(Document, doc.id)
        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "failed")


if __name__ == "__main__":
    unittest.main()
