from datetime import datetime

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    # doc_type tells us "what kind of doc is this?" (notes/transcript/prd/email)
    doc_type: str = Field(default="notes", min_length=1, max_length=50)

    # filename is optional because user may paste text without a file
    filename: str | None = Field(default=None, max_length=255)

    # text is required; empty text should be rejected
    text: str = Field(min_length=1)


class DocumentCreateResponse(BaseModel):
    document_id: str
    status: str


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    error: str | None = None
    processing_started_at: datetime | None = None
    indexed_at: datetime | None = None


class DocumentListItemResponse(BaseModel):
    document_id: str
    meeting_id: str
    doc_type: str
    filename: str | None = None
    status: str
    error: str | None = None
    processing_started_at: datetime | None = None
    indexed_at: datetime | None = None
