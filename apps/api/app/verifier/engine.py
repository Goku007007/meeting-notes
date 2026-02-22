import json
import logging
import uuid
from collections import Counter
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk
from app.schemas.verify import ActionItem, Issue, VerifyResponse

VERIFY_MODEL = "gpt-4.1-mini"
MAX_VERIFY_CHUNKS = 40
_openai_client: AsyncOpenAI | None = None
logger = logging.getLogger(__name__)

VAGUE_PHRASES = (
    "follow up",
    "handle",
    "fix",
    "take a look",
    "investigate",
    "sync",
    "touch base",
)


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI()
    return _openai_client


async def load_meeting_chunks(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    limit: int = MAX_VERIFY_CHUNKS,
) -> list[Chunk]:
    """Load broad meeting context for verifier (ordered, capped)."""
    stmt = (
        select(Chunk)
        .where(Chunk.meeting_id == meeting_id)
        .order_by(Chunk.chunk_index.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _build_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[chunk_id={chunk.id}] {chunk.text}" for chunk in chunks)


def _count_invalid_evidence_ids(result: VerifyResponse, allowed_ids: set[str]) -> int:
    invalid_count = 0
    for item in result.action_items:
        for evidence_id in item.evidence_chunk_ids:
            if evidence_id not in allowed_ids:
                invalid_count += 1
    for issue in result.issues:
        for evidence_id in issue.evidence_chunk_ids:
            if evidence_id not in allowed_ids:
                invalid_count += 1
    return invalid_count


def _strip_invalid_evidence_ids(result: VerifyResponse, allowed_ids: set[str]) -> int:
    removed = 0
    for item in result.action_items:
        before = len(item.evidence_chunk_ids)
        item.evidence_chunk_ids = [e for e in item.evidence_chunk_ids if e in allowed_ids]
        removed += before - len(item.evidence_chunk_ids)

    for issue in result.issues:
        before = len(issue.evidence_chunk_ids)
        issue.evidence_chunk_ids = [e for e in issue.evidence_chunk_ids if e in allowed_ids]
        removed += before - len(issue.evidence_chunk_ids)
    return removed


def _dedupe_issues(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    deduped: list[Issue] = []
    for issue in issues:
        key = (issue.type, issue.description, tuple(issue.evidence_chunk_ids))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def _apply_rule_based_checks(result: VerifyResponse) -> None:
    """
    Add deterministic issues after LLM extraction.
    These checks are stable across model changes and easy to test.
    """
    generated: list[Issue] = []
    for item in result.action_items:
        if not item.owner:
            generated.append(
                Issue(
                    type="missing_owner",
                    description=f"Action item missing owner: {item.task}",
                    evidence_chunk_ids=item.evidence_chunk_ids,
                )
            )
        if not item.due_date:
            generated.append(
                Issue(
                    type="missing_due_date",
                    description=f"Action item missing due date: {item.task}",
                    evidence_chunk_ids=item.evidence_chunk_ids,
                )
            )
        task_lower = item.task.lower()
        if any(phrase in task_lower for phrase in VAGUE_PHRASES):
            generated.append(
                Issue(
                    type="vague",
                    description=f"Action item is vague: {item.task}",
                    evidence_chunk_ids=item.evidence_chunk_ids,
                )
            )

    result.issues = _dedupe_issues(result.issues + generated)


async def _call_verifier_model(system_prompt: str, user_prompt: str) -> VerifyResponse:
    response = await get_openai_client().responses.create(
        model=VERIFY_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "verify_response",
                "schema": VerifyResponse.model_json_schema(),
                "strict": True,
            }
        },
    )

    if not response.output_text:
        return VerifyResponse(structured_summary="Unable to verify meeting notes.")

    try:
        payload: dict[str, Any] = json.loads(response.output_text)
    except json.JSONDecodeError:
        logger.exception("verifier returned non-json output")
        return VerifyResponse(structured_summary="Unable to verify meeting notes.")

    return VerifyResponse.model_validate(payload)


async def verify_meeting(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    limit: int = MAX_VERIFY_CHUNKS,
) -> tuple[VerifyResponse, dict[str, Any]]:
    """
    Extract structured meeting artifacts and verifier issues from meeting chunks.
    Returns (VerifyResponse, meta).
    """
    # Step 6.2: load broad, ordered context for the whole meeting (not similarity top-k).
    chunks = await load_meeting_chunks(db, meeting_id, limit=limit)
    if not chunks:
        response = VerifyResponse(
            structured_summary="No meeting content available to verify.",
            issues=[
                Issue(
                    type="missing_context",
                    description="No chunks found for this meeting.",
                    evidence_chunk_ids=[],
                )
            ],
        )
        return response, {"had_retry": False, "invalid_reason_counts": {}}

    context = _build_context(chunks)
    allowed_ids = {str(c.id) for c in chunks}
    allowed_ids_sorted = sorted(allowed_ids)
    invalid_reason_counts: Counter[str] = Counter()
    had_retry = False

    base_system = (
        "You are a meeting-notes verifier. Use ONLY the provided CONTEXT. "
        "Extract decisions, action items, open questions, and issues. "
        "Every action item and issue should include evidence_chunk_ids from CONTEXT."
    )
    base_user = (
        "Return a VerifyResponse JSON object.\n"
        "Keep summaries concise and factual.\n"
        f"CONTEXT:\n{context}"
    )

    # Step 6.2: first-pass model extraction using strict VerifyResponse JSON schema.
    result = await _call_verifier_model(base_system, base_user)
    invalid_first = _count_invalid_evidence_ids(result, allowed_ids)
    if invalid_first > 0:
        invalid_reason_counts["invalid_evidence_id"] += invalid_first
        had_retry = True

        # Step 6.2: one retry with explicit allowed IDs to force grounded evidence output.
        strict_system = (
            f"{base_system}\n\n"
            "GROUNDING RULES:\n"
            "- You MUST only use evidence_chunk_ids from ALLOWED_CHUNK_IDS.\n"
            "- If no evidence exists, return empty evidence_chunk_ids.\n"
            "- Do not invent IDs.\n\n"
            "ALLOWED_CHUNK_IDS:\n"
            f"{chr(10).join(f'- {cid}' for cid in allowed_ids_sorted)}"
        )
        result = await _call_verifier_model(strict_system, base_user)
        invalid_second = _count_invalid_evidence_ids(result, allowed_ids)
        if invalid_second > 0:
            invalid_reason_counts["invalid_evidence_id"] += invalid_second
            # Step 6.2 safe fallback: strip invalid IDs and attach a missing_context issue.
            removed = _strip_invalid_evidence_ids(result, allowed_ids)
            if removed > 0:
                result.issues.append(
                    Issue(
                        type="missing_context",
                        description=(
                            "Some evidence_chunk_ids could not be validated against retrieved chunks "
                            "and were removed."
                        ),
                        evidence_chunk_ids=[],
                    )
                )

    # Step 6.2: deterministic post-checks (missing owner/due date, vague tasks).
    _apply_rule_based_checks(result)
    result.had_retry = had_retry
    result.invalid_reason_counts = dict(invalid_reason_counts)

    meta = {
        "had_retry": had_retry,
        "invalid_reason_counts": dict(invalid_reason_counts),
        "retrieved_chunk_ids": [str(c.id) for c in chunks],
        "model": VERIFY_MODEL,
    }
    return result, meta
