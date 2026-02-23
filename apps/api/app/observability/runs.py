import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run


async def log_chat_run(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    question: str,
    retrieved_chunk_ids: list[str],
    citations: list[dict],
    response_payload: dict[str, Any] | None,
    had_retry: bool,
    invalid_reason_counts: dict[str, int],
    latency_ms: int,
    model: str,
    embedding_model: str,
) -> Run:
    """
    Persist one chat pipeline run for auditability and debugging.

    Keep this write path centralized so all endpoints log runs in a consistent shape.
    """
    run = Run(
        meeting_id=meeting_id,
        run_type="chat",
        input_text=question,
        retrieved_chunk_ids=retrieved_chunk_ids,
        response_citations=citations,
        response_json=response_payload,
        had_retry=had_retry,
        invalid_citation_reasons=invalid_reason_counts,
        latency_ms=latency_ms,
        model=model,
        embedding_model=embedding_model,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def log_verify_run(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    retrieved_chunk_ids: list[str],
    verify_payload: dict[str, Any],
    had_retry: bool,
    invalid_reason_counts: dict[str, int],
    latency_ms: int,
    model: str,
) -> Run:
    """
    Persist one verify pipeline run.

    v1 note: verify JSON is stored in response_citations as a single-item list
    so the existing Run schema can be reused without migration.
    """
    run = Run(
        meeting_id=meeting_id,
        run_type="verify",
        input_text="verify",
        retrieved_chunk_ids=retrieved_chunk_ids,
        response_citations=[],
        response_json=verify_payload,
        had_retry=had_retry,
        invalid_citation_reasons=invalid_reason_counts,
        latency_ms=latency_ms,
        model=model,
        embedding_model="not_applicable",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run
