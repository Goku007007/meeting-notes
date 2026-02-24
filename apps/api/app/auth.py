from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os
import secrets
import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db
from app.db.models import Document, GuestSession, Meeting
from app.storage import delete_upload_object

bearer_scheme = HTTPBearer(auto_error=False)
_SESSION_TOUCH_INTERVAL = timedelta(minutes=5)
SESSION_IDLE_TTL_HOURS = int(os.getenv("GUEST_SESSION_IDLE_TTL_HOURS", "168"))
SESSION_MAX_AGE_HOURS = int(os.getenv("GUEST_SESSION_MAX_AGE_HOURS", "720"))
GUEST_SESSION_COOKIE_NAME = os.getenv("GUEST_SESSION_COOKIE_NAME", "mn_guest_token")
logger = logging.getLogger(__name__)


def _is_expired(session: GuestSession, now: datetime) -> bool:
    if SESSION_IDLE_TTL_HOURS > 0:
        if session.last_seen_at <= now - timedelta(hours=SESSION_IDLE_TTL_HOURS):
            return True
    if SESSION_MAX_AGE_HOURS > 0:
        if session.created_at <= now - timedelta(hours=SESSION_MAX_AGE_HOURS):
            return True
    return False


def get_session_expires_at(session: GuestSession) -> datetime | None:
    expirations: list[datetime] = []
    if SESSION_IDLE_TTL_HOURS > 0:
        expirations.append(session.last_seen_at + timedelta(hours=SESSION_IDLE_TTL_HOURS))
    if SESSION_MAX_AGE_HOURS > 0:
        expirations.append(session.created_at + timedelta(hours=SESSION_MAX_AGE_HOURS))
    if not expirations:
        return None
    return min(expirations)


async def invalidate_guest_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    storage_result = await db.execute(
        select(Document.storage_path)
        .join(Meeting, Meeting.id == Document.meeting_id)
        .where(Meeting.session_id == session_id)
        .where(Document.storage_path.is_not(None))
    )
    storage_paths = [row[0] for row in storage_result.all() if row[0]]

    # Delete owned meetings first so all dependent rows are dropped via CASCADE.
    await db.execute(delete(Meeting).where(Meeting.session_id == session_id))
    await db.execute(delete(GuestSession).where(GuestSession.id == session_id))
    await db.commit()

    for storage_path in storage_paths:
        try:
            delete_upload_object(storage_path)
        except Exception:
            logger.exception("failed to delete storage object during session invalidation")


async def cleanup_expired_guest_sessions(db: AsyncSession) -> int:
    now = datetime.utcnow()
    filters = []
    if SESSION_IDLE_TTL_HOURS > 0:
        filters.append(GuestSession.last_seen_at <= now - timedelta(hours=SESSION_IDLE_TTL_HOURS))
    if SESSION_MAX_AGE_HOURS > 0:
        filters.append(GuestSession.created_at <= now - timedelta(hours=SESSION_MAX_AGE_HOURS))
    if not filters:
        return 0

    result = await db.execute(select(GuestSession.id).where(or_(*filters)))
    expired_ids = [row[0] for row in result.all()]
    if not expired_ids:
        return 0

    storage_result = await db.execute(
        select(Document.storage_path)
        .join(Meeting, Meeting.id == Document.meeting_id)
        .where(Meeting.session_id.in_(expired_ids))
        .where(Document.storage_path.is_not(None))
    )
    storage_paths = [row[0] for row in storage_result.all() if row[0]]

    await db.execute(delete(Meeting).where(Meeting.session_id.in_(expired_ids)))
    await db.execute(delete(GuestSession).where(GuestSession.id.in_(expired_ids)))
    await db.commit()

    for storage_path in storage_paths:
        try:
            delete_upload_object(storage_path)
        except Exception:
            logger.exception("failed to delete storage object during expired-session cleanup")
    return len(expired_ids)


async def get_guest_session_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> GuestSession | None:
    token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials.strip()
    if not token:
        token = (request.cookies.get(GUEST_SESSION_COOKIE_NAME) or "").strip()
    if not token:
        return None

    result = await db.execute(select(GuestSession).where(GuestSession.token == token))
    session = result.scalar_one_or_none()
    if session is None:
        return None

    now = datetime.utcnow()
    if _is_expired(session, now):
        await invalidate_guest_session(db, session.id)
        return None

    if (now - session.last_seen_at) >= _SESSION_TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.commit()

    return session


async def require_guest_session(
    session: GuestSession | None = Depends(get_guest_session_optional),
) -> GuestSession:
    if session is None:
        raise HTTPException(status_code=401, detail="missing, expired, or invalid authorization token")
    return session


def generate_guest_token() -> str:
    return secrets.token_urlsafe(32)


async def create_guest_session(db: AsyncSession) -> GuestSession:
    session = GuestSession(
        id=uuid.uuid4(),
        token=generate_guest_token(),
        created_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session
