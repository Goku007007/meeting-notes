from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)


class Citation(BaseModel):
    chunk_id: str
    quote: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    run_id: str | None = None


class ChatHistoryTurn(BaseModel):
    run_id: str
    question: str
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime


class ChatFeedbackRequest(BaseModel):
    run_id: str
    verdict: str = Field(min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=1000)
