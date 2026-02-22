import json
import uuid
import logging
import os
from collections import Counter
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk
from app.ai.grounding import validate_citations

CHAT_MODEL = "gpt-4.1-mini"
_openai_client: AsyncOpenAI | None = None
logger = logging.getLogger(__name__)
DEBUG_GROUNDING = os.getenv("DEBUG_GROUNDING", "false").strip().lower() in {"1", "true", "yes", "on"}


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI()
    return _openai_client


async def retrieve_similar_chunks(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[Chunk]:
    # Vector retrieval: same meeting only, nearest chunks first by cosine distance.
    stmt = (
        select(Chunk)
        .where(Chunk.meeting_id == meeting_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _build_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[chunk_id={chunk.id}] {chunk.text}" for chunk in chunks)


async def answer_with_citations(
    question: str,
    chunks: list[Chunk],
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Allowlist used by guardrails: citations must point only to retrieved chunks.
    allowed = {str(c.id): c.text for c in chunks}
    allowed_ids = list(allowed.keys())
    context = _build_context(chunks)
    had_retry = False
    invalid_reason_counts: Counter[str] = Counter()

    base_system = (
        "You are a grounded assistant. Use only the provided CONTEXT. "
        "If the context is insufficient, say you don't know. "
        "Citations must reference chunk_id values from context and include exact quotes."
    )
    schema = {
        "type": "json_schema",
        "name": "grounded_answer",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "answer": {"type": "string"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "chunk_id": {"type": "string"},
                            "quote": {"type": "string"},
                        },
                        "required": ["chunk_id", "quote"],
                    },
                },
            },
            "required": ["answer", "citations"],
        },
        "strict": True,
    }

    async def _call_model(system_text: str, user_text: str) -> dict:
        response = await get_openai_client().responses.create(
            model=CHAT_MODEL,
            input=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
            text={"format": schema},
        )
        if not response.output_text:
            return {"answer": "I don't know based on the provided context.", "citations": []}
        try:
            return json.loads(response.output_text)
        except json.JSONDecodeError:
            return {"answer": "I don't know based on the provided context.", "citations": []}

    result = await _call_model(
        base_system,
        f"QUESTION:\n{question}\n\nCONTEXT:\n{context}",
    )
    # First-pass validation catches fabricated IDs/quotes before returning to caller.
    valid, invalid = validate_citations(result.get("citations"), allowed)
    invalid_reason_counts.update(str(item.get("reason", "unknown")) for item in invalid)
    if DEBUG_GROUNDING:
        reason_counts = Counter(str(item.get("reason", "unknown")) for item in invalid)
        logger.info(
            "grounding.validation first_pass valid=%d invalid=%d reasons=%s",
            len(valid),
            len(invalid),
            dict(reason_counts),
        )
    answer_text = str(result.get("answer", "")).strip()
    needs_retry = bool(invalid) or (not valid and bool(answer_text))
    if DEBUG_GROUNDING:
        logger.info("grounding.retry needed=%s", needs_retry)

    if needs_retry:
        had_retry = True
        # Retry with explicit allowed IDs + verbatim quote rules to recover invalid output.
        strict_system = (
            f"{base_system}\n\n"
            "ALLOWED_CHUNK_IDS:\n"
            f"{chr(10).join(f'- {cid}' for cid in allowed_ids)}\n\n"
            "CITATION RULES:\n"
            "- You MUST only use chunk_ids from the allowed list.\n"
            "- Each quote must be copied verbatim from the chunk text.\n"
            "- If you cannot answer using the context, say you don't know and return empty citations."
        )
        retry = await _call_model(
            strict_system,
            f"QUESTION:\n{question}\n\nCONTEXT:\n{context}",
        )
        valid, invalid = validate_citations(retry.get("citations"), allowed)
        invalid_reason_counts.update(str(item.get("reason", "unknown")) for item in invalid)
        if DEBUG_GROUNDING:
            reason_counts = Counter(str(item.get("reason", "unknown")) for item in invalid)
            logger.info(
                "grounding.validation retry_pass valid=%d invalid=%d reasons=%s",
                len(valid),
                len(invalid),
                dict(reason_counts),
            )
        answer_text = str(retry.get("answer", "")).strip()

    if not valid:
        # Safe fallback: never return unverified citations.
        return (
            {"answer": "I don't know based on the provided notes.", "citations": []},
            {"had_retry": had_retry, "invalid_reason_counts": dict(invalid_reason_counts)},
        )

    # Return both API payload and run metadata for observability logging.
    return (
        {"answer": answer_text or "I don't know based on the provided notes.", "citations": valid},
        {"had_retry": had_retry, "invalid_reason_counts": dict(invalid_reason_counts)},
    )
