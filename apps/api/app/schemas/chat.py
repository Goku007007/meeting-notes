from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


class Citation(BaseModel):
    chunk_id: str
    quote: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
