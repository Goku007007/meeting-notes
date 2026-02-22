import uuid

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id",ondelete="CASCADE"), index = True, nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id",ondelete="CASCADE"), index = True, nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id",ondelete="CASCADE"), index = True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Current pipeline type; kept explicit so future run types (verify/reindex) fit same table.
    run_type: Mapped[str] = mapped_column(String(20), nullable=False, default="chat")
    # Original user question that triggered this run.
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Chunk IDs chosen by retrieval before generation.
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Final citations returned to the caller.
    response_citations: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    # Guardrail metadata for debugging citation quality.
    had_retry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invalid_citation_reasons: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False, default=dict)
    # End-to-end chat latency in milliseconds.
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # Model versions used by this run for reproducibility.
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
