import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select, text

from app.db.models import Base, GuestSession, Meeting, Run
from app.db.session import SessionLocal, engine
from app.jobs.indexing import index_document_async
from app.main import create_document, chat_with_meeting
from app.schemas.chat import ChatRequest
from app.schemas.documents import DocumentCreate


def _fake_vec() -> list[float]:
    return [0.0] * 1536


async def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
    return [_fake_vec() for _ in texts]


class ChatIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Fresh engine per test loop avoids asyncpg "different loop" connection errors.
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

    async def _create_meeting(self) -> str:
        meeting = Meeting(title=f"it-{uuid.uuid4()}", session_id=self.session.id)
        self.db.add(meeting)
        await self.db.commit()
        await self.db.refresh(meeting)
        return str(meeting.id)

    async def _ingest_doc(self, meeting_id: str, text_value: str) -> str:
        payload = DocumentCreate(doc_type="notes", filename="it.txt", text=text_value)
        result = await create_document(
            uuid.UUID(meeting_id),
            payload,
            self.request,
            self.session,
            self.db,
        )
        self.assertEqual(result.status, "pending")
        return result.document_id

    async def _latest_run(self, meeting_id: str) -> Run:
        result = await self.db.execute(
            select(Run)
            .where(Run.meeting_id == uuid.UUID(meeting_id))
            .order_by(Run.created_at.desc())
        )
        run = result.scalars().first()
        self.assertIsNotNone(run)
        return run

    async def test_chat_citations_in_retrieved_ids_pass_case(self) -> None:
        captured_retrieved_ids: set[str] = set()

        async def _good_answer(question: str, chunks: list) -> tuple[dict, dict]:
            cid = str(chunks[0].id)
            quote = str(chunks[0].text).split(".")[0]
            return (
                {"answer": "Grounded answer", "citations": [{"chunk_id": cid, "quote": quote}]},
                {"had_retry": False, "invalid_reason_counts": {}},
            )

        async def _capture_retrieve(db, meeting_id, query_embedding, top_k=6):
            from app.ai.client import retrieve_similar_chunks as real_retrieve

            # Capture actual retrieval output so assertions reflect real runtime behavior.
            rows = await real_retrieve(db, meeting_id, query_embedding, top_k)
            captured_retrieved_ids.clear()
            captured_retrieved_ids.update(str(r.id) for r in rows)
            return rows

        with patch("app.main.embed_texts", _fake_embed_texts), patch(
            "app.main.answer_with_citations", _good_answer
        ), patch(
            "app.main.retrieve_similar_chunks", _capture_retrieve
        ), patch(
            "app.main.enqueue_index_document", lambda _document_id: "queued"
        ), patch(
            "app.jobs.indexing.embed_texts", _fake_embed_texts
        ):
            meeting_id = await self._create_meeting()
            doc_id = await self._ingest_doc(meeting_id, "We decided to ship Friday. Alice owns QA.")
            await index_document_async(doc_id)
            response = await chat_with_meeting(
                uuid.UUID(meeting_id),
                ChatRequest(question="What did we decide?"),
                self.request,
                self.session,
                self.db,
            )
            # Response must cite only retrieved chunks.
            for c in response.citations:
                self.assertIn(c.chunk_id, captured_retrieved_ids)
            # Observability row should mirror what the endpoint returned/computed.
            run = await self._latest_run(meeting_id)
            self.assertEqual(run.run_type, "chat")
            self.assertEqual(run.input_text, "What did we decide?")
            self.assertEqual(set(run.retrieved_chunk_ids), captured_retrieved_ids)
            self.assertEqual(run.response_citations, response.model_dump()["citations"])
            self.assertFalse(run.had_retry)
            self.assertEqual(run.invalid_citation_reasons, {})
            self.assertEqual(run.model, "gpt-4.1-mini")
            self.assertEqual(run.embedding_model, "text-embedding-3-small")
            self.assertGreaterEqual(run.latency_ms, 0)

    async def test_chat_citations_not_in_retrieved_ids_fail_case(self) -> None:
        captured_retrieved_ids: set[str] = set()

        async def _bad_answer(question: str, chunks: list) -> tuple[dict, dict]:
            return (
                {
                    "answer": "Grounded answer",
                    "citations": [{"chunk_id": "00000000-0000-0000-0000-000000000000", "quote": "fake quote"}],
                },
                {"had_retry": True, "invalid_reason_counts": {"chunk_id_not_allowed": 1}},
            )

        async def _capture_retrieve(db, meeting_id, query_embedding, top_k=6):
            from app.ai.client import retrieve_similar_chunks as real_retrieve

            rows = await real_retrieve(db, meeting_id, query_embedding, top_k)
            captured_retrieved_ids.clear()
            captured_retrieved_ids.update(str(r.id) for r in rows)
            return rows

        with patch("app.main.embed_texts", _fake_embed_texts), patch(
            "app.main.answer_with_citations", _bad_answer
        ), patch(
            "app.main.retrieve_similar_chunks", _capture_retrieve
        ), patch(
            "app.main.enqueue_index_document", lambda _document_id: "queued"
        ), patch(
            "app.jobs.indexing.embed_texts", _fake_embed_texts
        ):
            meeting_id = await self._create_meeting()
            doc_id = await self._ingest_doc(meeting_id, "Budget approved after legal review.")
            await index_document_async(doc_id)
            response = await chat_with_meeting(
                uuid.UUID(meeting_id),
                ChatRequest(question="What was approved?"),
                self.request,
                self.session,
                self.db,
            )
            # Negative-path assertion: citations in this mocked case are intentionally outside retrieved set.
            for c in response.citations:
                self.assertNotIn(c.chunk_id, captured_retrieved_ids)
            run = await self._latest_run(meeting_id)
            self.assertEqual(run.input_text, "What was approved?")
            self.assertEqual(set(run.retrieved_chunk_ids), captured_retrieved_ids)
            self.assertEqual(run.response_citations, response.model_dump()["citations"])
            self.assertTrue(run.had_retry)
            self.assertEqual(run.invalid_citation_reasons, {"chunk_id_not_allowed": 1})


if __name__ == "__main__":
    unittest.main()
