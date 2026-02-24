import unittest
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, text

from app.auth import cleanup_expired_guest_sessions, get_session_expires_at, invalidate_guest_session
from app.db.models import Base, GuestSession, Meeting
from app.db.session import SessionLocal, engine


class GuestSessionSecurityTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_cleanup_expired_guest_sessions_deletes_owned_meetings(self) -> None:
        now = datetime.utcnow()
        expired = GuestSession(
            token=f"expired-{uuid.uuid4()}",
            created_at=now - timedelta(days=40),
            last_seen_at=now - timedelta(days=10),
        )
        fresh = GuestSession(
            token=f"fresh-{uuid.uuid4()}",
            created_at=now - timedelta(hours=1),
            last_seen_at=now - timedelta(minutes=5),
        )
        self.db.add_all([expired, fresh])
        await self.db.flush()

        self.db.add_all(
            [
                Meeting(title=f"old-{uuid.uuid4()}", session_id=expired.id),
                Meeting(title=f"new-{uuid.uuid4()}", session_id=fresh.id),
            ]
        )
        await self.db.commit()

        removed = await cleanup_expired_guest_sessions(self.db)
        self.assertEqual(removed, 1)

        expired_check = await self.db.execute(select(GuestSession).where(GuestSession.id == expired.id))
        fresh_check = await self.db.execute(select(GuestSession).where(GuestSession.id == fresh.id))
        self.assertIsNone(expired_check.scalar_one_or_none())
        self.assertIsNotNone(fresh_check.scalar_one_or_none())

        expired_meeting = await self.db.execute(select(Meeting).where(Meeting.session_id == expired.id))
        fresh_meeting = await self.db.execute(select(Meeting).where(Meeting.session_id == fresh.id))
        self.assertIsNone(expired_meeting.scalar_one_or_none())
        self.assertIsNotNone(fresh_meeting.scalar_one_or_none())

    async def test_invalidate_guest_session_deletes_session_and_meetings(self) -> None:
        session = GuestSession(token=f"invalidate-{uuid.uuid4()}")
        self.db.add(session)
        await self.db.flush()
        self.db.add(Meeting(title=f"meeting-{uuid.uuid4()}", session_id=session.id))
        await self.db.commit()

        await invalidate_guest_session(self.db, session.id)

        session_check = await self.db.execute(select(GuestSession).where(GuestSession.id == session.id))
        meetings_check = await self.db.execute(select(Meeting).where(Meeting.session_id == session.id))
        self.assertIsNone(session_check.scalar_one_or_none())
        self.assertIsNone(meetings_check.scalar_one_or_none())

    async def test_get_session_expires_at_returns_value(self) -> None:
        now = datetime.utcnow()
        session = GuestSession(
            token=f"expires-{uuid.uuid4()}",
            created_at=now - timedelta(hours=2),
            last_seen_at=now - timedelta(hours=1),
        )
        expires_at = get_session_expires_at(session)
        self.assertIsNotNone(expires_at)
        self.assertGreater(expires_at, now)


if __name__ == "__main__":
    unittest.main()
