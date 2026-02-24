from pydantic import BaseModel


class ChunkDetailResponse(BaseModel):
    chunk_id: str
    meeting_id: str
    document_id: str
    chunk_index: int
    text: str
    document_filename: str | None = None
    document_original_filename: str | None = None
    document_doc_type: str | None = None
