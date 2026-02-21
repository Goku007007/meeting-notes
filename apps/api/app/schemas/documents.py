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
    chunks_created: int
    