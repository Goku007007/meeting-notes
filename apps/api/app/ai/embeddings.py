from openai import AsyncOpenAI

EMBEDDING_MODEL = "text-embedding-3-small"

_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        # OPENAI_API_KEY is read from environment variables by the OpenAI SDK.
        _openai_client = AsyncOpenAI()
    return _openai_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = await get_openai_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]
