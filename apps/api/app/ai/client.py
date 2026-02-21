import json
import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk

CHAT_MODEL = "gpt-4.1-mini"
_openai_client: AsyncOpenAI | None = None


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


async def answer_with_citations(question: str, chunks: list[Chunk]) -> dict:
    context = _build_context(chunks)

    response = await get_openai_client().responses.create(
        model=CHAT_MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a grounded assistant. Use only the provided CONTEXT. "
                    "If the context is insufficient, say you don't know. "
                    "Citations must reference chunk_id values from context and include exact quotes."
                ),
            },
            {
                "role": "user",
                "content": f"QUESTION:\n{question}\n\nCONTEXT:\n{context}",
            },
        ],
        text={
            "format": {
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
        },
    )

    if not response.output_text:
        return {"answer": "I don't know based on the provided context.", "citations": []}

    return json.loads(response.output_text)
