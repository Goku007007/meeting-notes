from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
import os
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Meeting, Run


@dataclass(frozen=True)
class Limits:
    per_minute_session_create_ip: int = int(os.getenv("RATE_LIMIT_SESSION_CREATE_PER_MINUTE_IP", "10"))
    per_minute_upload_ip: int = int(os.getenv("RATE_LIMIT_UPLOAD_PER_MINUTE_IP", "20"))
    per_minute_upload_session: int = int(os.getenv("RATE_LIMIT_UPLOAD_PER_MINUTE_SESSION", "30"))
    per_minute_reindex_ip: int = int(os.getenv("RATE_LIMIT_REINDEX_PER_MINUTE_IP", "20"))
    per_minute_reindex_session: int = int(os.getenv("RATE_LIMIT_REINDEX_PER_MINUTE_SESSION", "30"))
    per_minute_chat_ip: int = int(os.getenv("RATE_LIMIT_CHAT_PER_MINUTE_IP", "60"))
    per_minute_chat_session: int = int(os.getenv("RATE_LIMIT_CHAT_PER_MINUTE_SESSION", "90"))
    per_minute_verify_ip: int = int(os.getenv("RATE_LIMIT_VERIFY_PER_MINUTE_IP", "15"))
    per_minute_verify_session: int = int(os.getenv("RATE_LIMIT_VERIFY_PER_MINUTE_SESSION", "20"))
    uploads_per_day: int = int(os.getenv("QUOTA_UPLOADS_PER_DAY", "200"))
    upload_mb_per_day: int = int(os.getenv("QUOTA_UPLOAD_MB_PER_DAY", "500"))
    chats_per_day: int = int(os.getenv("QUOTA_CHATS_PER_DAY", "1000"))
    verifies_per_day: int = int(os.getenv("QUOTA_VERIFIES_PER_DAY", "200"))
    max_active_index_jobs_per_session: int = int(os.getenv("MAX_ACTIVE_INDEX_JOBS_PER_SESSION", "25"))


_limits = Limits()
_window_seconds = 60.0
_ip_hits: dict[str, deque[float]] = defaultdict(deque)
_session_hits: dict[str, deque[float]] = defaultdict(deque)


def _raise_429(message: str, retry_after_seconds: int | None = None) -> None:
    detail: dict[str, int | str] = {"code": "rate_limited", "message": message}
    headers: dict[str, str] | None = None
    if retry_after_seconds is not None and retry_after_seconds > 0:
        detail["retry_after_seconds"] = retry_after_seconds
        headers = {"Retry-After": str(retry_after_seconds)}
    raise HTTPException(status_code=429, detail=detail, headers=headers)


def _enforce_window(bucket: dict[str, deque[float]], key: str, limit: int, label: str) -> None:
    if limit <= 0:
        return

    now = time.monotonic()
    values = bucket[key]
    while values and (now - values[0]) > _window_seconds:
        values.popleft()
    if len(values) >= limit:
        wait_for = max(1, int(_window_seconds - (now - values[0]))) if values else int(_window_seconds)
        _raise_429(f"Too many {label} requests. Please slow down and try again.", retry_after_seconds=wait_for)
    values.append(now)


def enforce_per_minute_limits(
    operation: str,
    ip: str | None,
    session_id: uuid.UUID | None,
) -> None:
    if operation == "session_create":
        ip_limit = _limits.per_minute_session_create_ip
        session_limit = 0
    elif operation == "upload":
        ip_limit = _limits.per_minute_upload_ip
        session_limit = _limits.per_minute_upload_session
    elif operation == "reindex":
        ip_limit = _limits.per_minute_reindex_ip
        session_limit = _limits.per_minute_reindex_session
    elif operation == "verify":
        ip_limit = _limits.per_minute_verify_ip
        session_limit = _limits.per_minute_verify_session
    else:
        ip_limit = _limits.per_minute_chat_ip
        session_limit = _limits.per_minute_chat_session

    if ip:
        _enforce_window(_ip_hits, f"{operation}:ip:{ip}", ip_limit, f"{operation} ip")
    if session_id is not None:
        _enforce_window(
            _session_hits,
            f"{operation}:session:{session_id}",
            session_limit,
            f"{operation} session",
        )


def _utc_day_start() -> datetime:
    # DB created_at columns in this project are timezone-naive UTC.
    # Keep quota boundary values naive as well to avoid asyncpg tz mismatch errors.
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def enforce_daily_upload_quotas(
    db: AsyncSession,
    session_id: uuid.UUID,
    incoming_bytes: int,
) -> None:
    day_start = _utc_day_start()
    result = await db.execute(
        select(func.count(Document.id), func.coalesce(func.sum(Document.size_bytes), 0))
        .join(Meeting, Meeting.id == Document.meeting_id)
        .where(Meeting.session_id == session_id)
        .where(Document.created_at >= day_start)
    )
    uploads_count, total_bytes = result.one()

    if int(uploads_count or 0) >= _limits.uploads_per_day:
        _raise_429("Daily upload quota exceeded for this session. Please try again tomorrow.")

    max_bytes = _limits.upload_mb_per_day * 1024 * 1024
    if int(total_bytes or 0) + incoming_bytes > max_bytes:
        _raise_429("Daily upload size quota exceeded for this session. Please try again tomorrow.")


async def enforce_daily_run_quotas(
    db: AsyncSession,
    session_id: uuid.UUID,
    run_type: str,
) -> None:
    day_start = _utc_day_start()
    result = await db.execute(
        select(func.count(Run.id))
        .join(Meeting, Meeting.id == Run.meeting_id)
        .where(Meeting.session_id == session_id)
        .where(Run.created_at >= day_start)
        .where(Run.run_type == run_type)
    )
    count = int(result.scalar_one() or 0)
    if run_type == "verify":
        if count >= _limits.verifies_per_day:
            _raise_429("Daily verify quota exceeded for this session. Please try again tomorrow.")
        return
    if count >= _limits.chats_per_day:
        _raise_429("Daily chat quota exceeded for this session. Please try again tomorrow.")


async def enforce_index_queue_capacity(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    if _limits.max_active_index_jobs_per_session <= 0:
        return

    result = await db.execute(
        select(func.count(Document.id))
        .join(Meeting, Meeting.id == Document.meeting_id)
        .where(Meeting.session_id == session_id)
        .where(Document.status.in_(["pending", "processing"]))
    )
    active_count = int(result.scalar_one() or 0)
    if active_count >= _limits.max_active_index_jobs_per_session:
        _raise_429(
            "Too many documents are currently indexing for this session. Please wait and retry.",
            retry_after_seconds=30,
        )
