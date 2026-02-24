import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select

from app.ai.embeddings import embed_texts
from app.auth import cleanup_expired_guest_sessions
from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.ingestion.chunking import chunk_text
from app.processing import extract_text_from_file
from app.storage import materialize_storage_path

STALE_PROCESSING_MINUTES = int(os.getenv("STALE_PROCESSING_MINUTES", "30"))
EXTRACTION_TIMEOUT_SECONDS = int(os.getenv("EXTRACTION_TIMEOUT_SECONDS", "120"))
MAX_EXTRACTED_TEXT_CHARS = int(os.getenv("MAX_EXTRACTED_TEXT_CHARS", str(2_000_000)))
MAX_CHUNKS_PER_DOCUMENT = int(os.getenv("MAX_CHUNKS_PER_DOCUMENT", "600"))
logger = logging.getLogger(__name__)


def index_document(document_id: str) -> None:
    """
    RQ entrypoint (sync): index a document in the background.
    RQ workers call top-level sync callables, so this wraps async logic.
    """
    asyncio.run(index_document_async(document_id))


async def index_document_async(document_id: str) -> None:
    doc_uuid = uuid.UUID(str(document_id))

    async with SessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        doc = result.scalar_one_or_none()
        if doc is None:
            # Nothing to do if document was deleted before worker picked up the job.
            return

        try:
            # Mark work started and clear previous failure info (reindex-safe).
            doc.status = "processing"
            doc.error = None
            doc.processing_started_at = datetime.now(timezone.utc)
            doc.indexed_at = None
            await db.commit()

            # Capture previous chunk IDs so we can clean them up only after new chunks are committed.
            previous_ids_result = await db.execute(select(Chunk.id).where(Chunk.document_id == doc.id))
            previous_chunk_ids = [row[0] for row in previous_ids_result.all()]

            # File-uploaded docs may not have raw_text yet; extract it in worker.
            if not doc.raw_text.strip():
                if not doc.storage_path:
                    raise ValueError("document has no raw_text and no storage_path for extraction")
                # Run extraction in a thread with timeout so one bad file cannot stall a worker.
                with materialize_storage_path(doc.storage_path) as local_path:
                    doc.raw_text = await asyncio.wait_for(
                        asyncio.to_thread(extract_text_from_file, local_path, doc.mime_type),
                        timeout=EXTRACTION_TIMEOUT_SECONDS,
                    )

            if len(doc.raw_text) > MAX_EXTRACTED_TEXT_CHARS:
                raise ValueError(
                    f"extracted text exceeds limit ({MAX_EXTRACTED_TEXT_CHARS} chars)"
                )

            pieces = chunk_text(doc.raw_text)
            if not pieces:
                raise ValueError("document produced no chunks after extraction")
            if MAX_CHUNKS_PER_DOCUMENT > 0 and len(pieces) > MAX_CHUNKS_PER_DOCUMENT:
                raise ValueError(
                    f"document produced too many chunks ({len(pieces)} > {MAX_CHUNKS_PER_DOCUMENT})"
                )
            vectors = await embed_texts(pieces) if pieces else []
            if len(vectors) != len(pieces):
                raise ValueError("embedding count does not match chunk count")

            for i, piece in enumerate(pieces):
                db.add(
                    Chunk(
                        meeting_id=doc.meeting_id,
                        document_id=doc.id,
                        chunk_index=i,
                        text=piece,
                        embedding=vectors[i],
                    )
                )

            doc.status = "indexed"
            doc.error = None
            doc.processing_started_at = None
            doc.indexed_at = datetime.now(timezone.utc)
            await db.commit()

            # Best-effort cleanup of previous chunk set.
            # If this fails, we keep the newly indexed content available and can clean later.
            if previous_chunk_ids:
                try:
                    await db.execute(delete(Chunk).where(Chunk.id.in_(previous_chunk_ids)))
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception(
                        "index cleanup failed document_id=%s old_chunk_count=%d",
                        document_id,
                        len(previous_chunk_ids),
                    )
        except Exception as exc:
            await db.rollback()
            error_message = str(exc).strip()
            if isinstance(exc, asyncio.TimeoutError):
                error_message = (
                    f"extraction timed out after {EXTRACTION_TIMEOUT_SECONDS} seconds"
                )
            if not error_message:
                error_message = "document processing failed"

            # Best effort: persist failure state so UI/users can see what happened.
            result = await db.execute(select(Document).where(Document.id == doc_uuid))
            failed_doc = result.scalar_one_or_none()
            if failed_doc is not None:
                failed_doc.status = "failed"
                failed_doc.error = error_message[:4000]
                failed_doc.processing_started_at = None
                failed_doc.indexed_at = None
                await db.commit()

            # Re-raise so queue systems can mark the job failed/retriable.
            raise


def reap_stale_processing_documents(max_age_minutes: int | None = None) -> int:
    """
    RQ/CLI entrypoint: mark documents stuck in processing as failed.
    This covers cases where a worker dies mid-job and status would otherwise hang.
    """
    return asyncio.run(reap_stale_processing_documents_async(max_age_minutes=max_age_minutes))


async def reap_stale_processing_documents_async(max_age_minutes: int | None = None) -> int:
    max_age = max_age_minutes if max_age_minutes is not None else STALE_PROCESSING_MINUTES
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age)

    async with SessionLocal() as db:
        expired_sessions = await cleanup_expired_guest_sessions(db)
        if expired_sessions:
            logger.info("session cleanup removed %d expired guest sessions", expired_sessions)

        result = await db.execute(
            select(Document)
            .where(Document.status == "processing")
            .where(
                or_(
                    Document.processing_started_at.is_(None),
                    Document.processing_started_at < cutoff,
                )
            )
        )
        stale_docs = list(result.scalars().all())
        if not stale_docs:
            return 0

        for doc in stale_docs:
            doc.status = "failed"
            doc.error = f"processing timed out after {max_age} minutes"
            doc.processing_started_at = None
            doc.indexed_at = None

        await db.commit()
        return len(stale_docs)
