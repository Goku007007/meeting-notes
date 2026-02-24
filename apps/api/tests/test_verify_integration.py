import re
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select, text

from app.db.models import Base, Chunk, Document, GuestSession, Meeting, Run
from app.db.session import SessionLocal, engine
from app.main import verify_endpoint
from app.schemas.verify import ActionItem, Issue, VerifyResponse


def _fake_vec() -> list[float]:
    return [0.0] * 1536


class VerifyIntegrationTests(unittest.IsolatedAsyncioTestCase):
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

    async def _create_meeting_with_chunk(self, chunk_text: str) -> tuple[str, str]:
        meeting = Meeting(title=f"verify-it-{uuid.uuid4()}", session_id=self.session.id)
        self.db.add(meeting)
        await self.db.flush()

        doc = Document(
            meeting_id=meeting.id,
            doc_type="notes",
            filename="verify.txt",
            raw_text=chunk_text,
        )
        self.db.add(doc)
        await self.db.flush()

        chunk = Chunk(
            meeting_id=meeting.id,
            document_id=doc.id,
            chunk_index=0,
            text=chunk_text,
            embedding=_fake_vec(),
        )
        self.db.add(chunk)
        await self.db.commit()
        return str(meeting.id), str(chunk.id)

    async def _latest_verify_run(self, meeting_id: str) -> Run:
        result = await self.db.execute(
            select(Run)
            .where(Run.meeting_id == uuid.UUID(meeting_id))
            .where(Run.run_type == "verify")
            .order_by(Run.created_at.desc())
        )
        run = result.scalars().first()
        self.assertIsNotNone(run)
        return run

    async def test_verify_adds_deterministic_issues(self) -> None:
        # Step 6.4 Test 1:
        # Verify deterministic rule checks append missing_owner/missing_due_date/vague.
        meeting_id, chunk_id = await self._create_meeting_with_chunk("Follow up with legal on contract terms.")

        async def _mock_call(system_prompt: str, user_prompt: str) -> VerifyResponse:
            match = re.search(r"\[chunk_id=([^\]]+)\]", user_prompt)
            cid = match.group(1) if match else chunk_id
            return VerifyResponse(
                structured_summary="Summary",
                action_items=[
                    ActionItem(
                        task="Follow up with legal",
                        owner=None,
                        due_date=None,
                        evidence_chunk_ids=[cid],
                    )
                ],
                decisions=[],
                open_questions=[],
                issues=[],
            )

        with patch("app.verifier.engine._call_verifier_model", _mock_call):
            response = await verify_endpoint(uuid.UUID(meeting_id), self.request, self.session, self.db)

        issue_types = {issue.type for issue in response.issues}
        self.assertIn("missing_owner", issue_types)
        self.assertIn("missing_due_date", issue_types)
        self.assertIn("vague", issue_types)

        allowed_ids = {chunk_id}
        for item in response.action_items:
            self.assertTrue(set(item.evidence_chunk_ids).issubset(allowed_ids))
        for issue in response.issues:
            self.assertTrue(set(issue.evidence_chunk_ids).issubset(allowed_ids))

    async def test_verify_strips_invalid_evidence_and_adds_missing_context_issue(self) -> None:
        # Step 6.4 Test 2:
        # Invalid evidence IDs should be stripped and missing_context should be added.
        meeting_id, chunk_id = await self._create_meeting_with_chunk("Shipping discussion with constraints.")

        async def _mock_call(system_prompt: str, user_prompt: str) -> VerifyResponse:
            return VerifyResponse(
                structured_summary="Summary",
                action_items=[
                    ActionItem(
                        task="Investigate blocker",
                        owner="Alex",
                        due_date="2026-03-01",
                        evidence_chunk_ids=["not-a-valid-chunk-id"],
                    )
                ],
                decisions=[],
                open_questions=[],
                issues=[Issue(type="other", description="Potential risk", evidence_chunk_ids=["also-invalid"])],
            )

        with patch("app.verifier.engine._call_verifier_model", _mock_call):
            response = await verify_endpoint(uuid.UUID(meeting_id), self.request, self.session, self.db)

        allowed_ids = {chunk_id}
        for item in response.action_items:
            self.assertTrue(set(item.evidence_chunk_ids).issubset(allowed_ids))
        for issue in response.issues:
            self.assertTrue(set(issue.evidence_chunk_ids).issubset(allowed_ids))

        issue_types = {issue.type for issue in response.issues}
        self.assertIn("missing_context", issue_types)
        self.assertTrue(response.had_retry)

    async def test_verify_creates_run_row(self) -> None:
        # Step 6.4 Test 3:
        # /verify should create one run row with verify-specific metadata.
        meeting_id, chunk_id = await self._create_meeting_with_chunk("Decision: ship Friday.")

        async def _mock_call(system_prompt: str, user_prompt: str) -> VerifyResponse:
            return VerifyResponse(
                structured_summary="Ship on Friday.",
                decisions=["Ship on Friday"],
                action_items=[],
                open_questions=[],
                issues=[],
            )

        with patch("app.verifier.engine._call_verifier_model", _mock_call):
            response = await verify_endpoint(uuid.UUID(meeting_id), self.request, self.session, self.db)

        run = await self._latest_verify_run(meeting_id)
        self.assertEqual(run.run_type, "verify")
        self.assertEqual(run.input_text, "verify")
        self.assertEqual(set(run.retrieved_chunk_ids), {chunk_id})
        self.assertEqual(run.response_citations, [])
        self.assertEqual(run.response_json, response.model_dump())


if __name__ == "__main__":
    unittest.main()
