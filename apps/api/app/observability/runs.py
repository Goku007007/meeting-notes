import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Run


async def log_chat_run(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    question: str,
    retrieved_chunk_ids: list[str],
    citations: list[dict],
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
