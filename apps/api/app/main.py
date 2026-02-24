from datetime import datetime, timezone
import ipaddress
from fastapi import Depends
from fastapi import File
from fastapi import FastAPI
from fastapi import Form
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi import UploadFile
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import logging
import os
from pathlib import Path
import time
import uuid

from dotenv import load_dotenv
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
import secrets

from app.auth import (
    GUEST_SESSION_COOKIE_NAME,
    SESSION_IDLE_TTL_HOURS,
    cleanup_expired_guest_sessions,
    create_guest_session,
    get_guest_session_optional,
    get_session_expires_at,
    invalidate_guest_session,
    require_guest_session,
)
from app.ai.client import CHAT_MODEL, answer_with_citations, retrieve_similar_chunks
from app.ai.embeddings import EMBEDDING_MODEL, embed_texts
from app.db.deps import get_db
from app.db.models import Chunk, Document, GuestSession, Meeting, Run, RunFeedback
from app.db.session import engine
from app.observability.runs import log_chat_run, log_verify_run
from app.processing import UnsupportedFormatError, validate_supported_upload
from app.rate_limit import enforce_daily_run_quotas, enforce_daily_upload_quotas, enforce_per_minute_limits
from app.rate_limit import enforce_index_queue_capacity
from app.schemas.chunks import ChunkDetailResponse
from app.schemas.documents import (
    DocumentCreate,
    DocumentCreateResponse,
    DocumentListItemResponse,
    DocumentStatusResponse,
)
from app.schemas.chat import ChatFeedbackRequest, ChatHistoryTurn, ChatRequest, ChatResponse
from app.schemas.meetings import MeetingResponse
from app.queue import enqueue_index_document, enqueue_reaper_job
from app.schemas.sessions import GuestSessionResponse
from app.schemas.verify import Issue, VerifyResponse
from app.storage import delete_upload_object, save_upload_bytes
from app.verifier.engine import verify_meeting

load_dotenv()


app = FastAPI()
logger = logging.getLogger(__name__)
DEBUG_GROUNDING = os.getenv("DEBUG_GROUNDING", "false").strip().lower() in {"1", "true", "yes", "on"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
MAX_FILES_PER_UPLOAD_REQUEST = int(os.getenv("MAX_FILES_PER_UPLOAD_REQUEST", "10"))
GUEST_SESSION_COOKIE_ENABLED = os.getenv("GUEST_SESSION_COOKIE_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
GUEST_SESSION_COOKIE_SECURE = os.getenv("GUEST_SESSION_COOKIE_SECURE", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
GUEST_SESSION_COOKIE_SAMESITE = os.getenv("GUEST_SESSION_COOKIE_SAMESITE", "lax").strip().lower()
if GUEST_SESSION_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    GUEST_SESSION_COOKIE_SAMESITE = "lax"
REINDEX_COOLDOWN_SECONDS = int(os.getenv("REINDEX_COOLDOWN_SECONDS", "120"))
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SECURITY_CSP = os.getenv(
    "SECURITY_CSP",
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
)
MAX_JSON_BODY_BYTES = int(os.getenv("MAX_JSON_BODY_BYTES", str(1 * 1024 * 1024)))
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "mn_csrf_token")
REQUIRE_CSRF_FOR_COOKIE_AUTH = os.getenv("REQUIRE_CSRF_FOR_COOKIE_AUTH", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "").strip()
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]
# Default local-dev safety net: allow localhost/127.0.0.1 on any port.
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)
TRUSTED_PROXY_CIDRS = [
    value.strip()
    for value in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",")
    if value.strip()
]
SECURITY_HSTS = os.getenv(
    "SECURITY_HSTS",
    "max-age=31536000; includeSubDomains" if APP_ENV in {"production", "staging"} else "",
).strip()
if APP_ENV in {"production", "staging"}:
    if any(origin == "*" for origin in CORS_ALLOW_ORIGINS):
        raise RuntimeError("Wildcard CORS origins are not allowed outside development.")
    regex_value = CORS_ALLOW_ORIGIN_REGEX.strip()
    if regex_value and regex_value in {".*", "^.*$"}:
        raise RuntimeError("Wildcard CORS origin regex is not allowed outside development.")

# Allow the local frontend app to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", SECURITY_CSP)
    if SECURITY_HSTS and request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", SECURITY_HSTS)
    return response


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.monotonic()
    response = await call_next(request)
    latency_ms = int((time.monotonic() - started) * 1000)
    response.headers.setdefault("X-Request-Id", request_id)

    token: str | None = None
    auth_header = (request.headers.get("authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = (request.cookies.get(GUEST_SESSION_COOKIE_NAME) or "").strip() or None
    session_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12] if token else None

    logger.info(
        "request request_id=%s method=%s path=%s status=%s latency_ms=%s session_hash=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
        session_hash,
    )
    return response


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if not REQUIRE_CSRF_FOR_COOKIE_AUTH:
        return await call_next(request)

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        path = request.url.path
        if path not in {"/sessions/guest"}:
            auth_header = request.headers.get("authorization", "").strip()
            uses_bearer = auth_header.lower().startswith("bearer ")
            has_session_cookie = bool((request.cookies.get(GUEST_SESSION_COOKIE_NAME) or "").strip())
            if has_session_cookie and not uses_bearer:
                csrf_cookie = (request.cookies.get(CSRF_COOKIE_NAME) or "").strip()
                csrf_header = (request.headers.get("x-csrf-token") or "").strip()
                if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "code": "csrf_failed",
                            "message": "CSRF validation failed for cookie-authenticated request.",
                        },
                    )
    return await call_next(request)


@app.middleware("http")
async def request_size_guard_middleware(request: Request, call_next):
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type and MAX_JSON_BODY_BYTES > 0:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > MAX_JSON_BODY_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "request_too_large",
                        "message": f"JSON body too large; max allowed is {MAX_JSON_BODY_BYTES} bytes.",
                    },
                )
    return await call_next(request)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # (optional safety) ensures pgvector extension exists
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Alembic is the only schema manager in runtime environments.

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    details: dict[str, str | bool] = {"database": False, "queue": False}
    try:
        await db.execute(text("SELECT 1"))
        details["database"] = True
    except Exception:
        logger.exception("readiness database check failed")

    try:
        queue = get_queue_for_health()
        queue.connection.ping()
        details["queue"] = True
    except Exception:
        logger.exception("readiness queue check failed")

    ok = bool(details["database"]) and bool(details["queue"])
    if not ok:
        raise HTTPException(status_code=503, detail={"ok": False, "checks": details})
    return {"ok": True, "checks": details}


@app.get("/health/worker")
async def worker_health():
    try:
        from rq import Worker
    except ModuleNotFoundError:
        raise HTTPException(status_code=500, detail="rq is not installed")

    queue = get_queue_for_health()
    workers = Worker.all(connection=queue.connection)
    return {"ok": len(workers) > 0, "worker_count": len(workers)}


@app.get("/")
def root():
    return {"message": "API is running try /health or /docs"}


def get_queue_for_health():
    # Lazy import helper so readiness endpoints can check Redis without circular imports.
    from app.queue import get_queue

    return get_queue()


def _client_ip(request: Request) -> str | None:
    direct_ip = request.client.host if request.client else None
    if not _is_trusted_proxy(direct_ip):
        return direct_ip

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        for value in forwarded_for.split(","):
            candidate = value.strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                continue
    return direct_ip


def _is_trusted_proxy(client_ip: str | None) -> bool:
    if not client_ip or not TRUSTED_PROXY_CIDRS:
        return False
    try:
        parsed_ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for cidr in TRUSTED_PROXY_CIDRS:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXY_CIDRS entry: %s", cidr)
            continue
        if parsed_ip in network:
            return True
    return False


async def _get_owned_meeting_or_404(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    session_id: uuid.UUID,
) -> Meeting:
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id).where(Meeting.session_id == session_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


async def _get_owned_document_or_404(
    db: AsyncSession,
    document_id: uuid.UUID,
    session_id: uuid.UUID,
) -> Document:
    result = await db.execute(
        select(Document)
        .join(Meeting, Meeting.id == Document.meeting_id)
        .where(Document.id == document_id)
        .where(Meeting.session_id == session_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    return document


def _normalize_upload_filename(filename: str | None) -> str:
    return Path(filename or "upload.bin").name


def _require_admin_token(x_admin_token: str | None) -> None:
    if not ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "admin_token_not_configured",
                "message": "Admin API token is not configured.",
            },
        )
    if not secrets.compare_digest((x_admin_token or "").strip(), ADMIN_API_TOKEN):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_admin_token", "message": "Invalid admin token."},
        )


def _set_guest_session_cookie(response: Response, token: str) -> None:
    if not GUEST_SESSION_COOKIE_ENABLED:
        return
    max_age_seconds: int | None = None
    if SESSION_IDLE_TTL_HOURS > 0:
        max_age_seconds = SESSION_IDLE_TTL_HOURS * 3600
    response.set_cookie(
        key=GUEST_SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=GUEST_SESSION_COOKIE_SECURE,
        samesite=GUEST_SESSION_COOKIE_SAMESITE,
        max_age=max_age_seconds,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(24),
        httponly=False,
        secure=GUEST_SESSION_COOKIE_SECURE,
        samesite=GUEST_SESSION_COOKIE_SAMESITE,
        max_age=max_age_seconds,
        path="/",
    )


def _clear_guest_session_cookie(response: Response) -> None:
    if not GUEST_SESSION_COOKIE_ENABLED:
        return
    response.delete_cookie(
        key=GUEST_SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=GUEST_SESSION_COOKIE_SECURE,
        samesite=GUEST_SESSION_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        secure=GUEST_SESSION_COOKIE_SECURE,
        samesite=GUEST_SESSION_COOKIE_SAMESITE,
    )


@app.post("/sessions/guest", response_model=GuestSessionResponse)
async def create_guest_session_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    enforce_per_minute_limits("session_create", _client_ip(request), None)
    await cleanup_expired_guest_sessions(db)
    session = await create_guest_session(db)
    _set_guest_session_cookie(response, session.token)
    expires_at = get_session_expires_at(session)
    return GuestSessionResponse(
        token=session.token,
        session_id=str(session.id),
        created_at=session.created_at,
        expires_at=expires_at,
    )


@app.post("/sessions/reset", response_model=GuestSessionResponse)
async def reset_guest_session(
    request: Request,
    response: Response,
    current_session: GuestSession | None = Depends(get_guest_session_optional),
    db: AsyncSession = Depends(get_db),
):
    enforce_per_minute_limits("session_create", _client_ip(request), None)
    if current_session is not None:
        await invalidate_guest_session(db, current_session.id)
    await cleanup_expired_guest_sessions(db)

    session = await create_guest_session(db)
    _set_guest_session_cookie(response, session.token)
    expires_at = get_session_expires_at(session)
    return GuestSessionResponse(
        token=session.token,
        session_id=str(session.id),
        created_at=session.created_at,
        expires_at=expires_at,
    )


@app.delete("/sessions/current")
async def delete_current_session(
    response: Response,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    await invalidate_guest_session(db, current_session.id)
    _clear_guest_session_cookie(response)
    return {"ok": True}


@app.post("/meetings")
async def create_meeting(
    title: str,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    meeting = Meeting(title = title)
    meeting.session_id = current_session.id
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting) #pulls generated fields like id back from DB
    return {"id": str(meeting.id), "title": meeting.title, "created_at": meeting.created_at}


@app.get("/meetings", response_model=list[MeetingResponse])
async def list_meetings(
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting)
        .where(Meeting.session_id == current_session.id)
        .order_by(Meeting.created_at.desc())
    )
    meetings = result.scalars().all()
    return [
        {"id": str(meeting.id), "title": meeting.title, "created_at": meeting.created_at}
        for meeting in meetings
    ]


@app.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: uuid.UUID,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    meeting = await _get_owned_meeting_or_404(db, meeting_id, current_session.id)
    return {"id": str(meeting.id), "title": meeting.title, "created_at": meeting.created_at}



#chunking

@app.post("/meetings/{meeting_id}/documents", response_model=DocumentCreateResponse)
async def create_document(
    meeting_id: uuid.UUID,
    payload: DocumentCreate,
    request: Request,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_meeting_or_404(db, meeting_id, current_session.id)
    enforce_per_minute_limits("upload", _client_ip(request), current_session.id)
    await enforce_daily_upload_quotas(
        db,
        current_session.id,
        len(payload.text.encode("utf-8", errors="ignore")),
    )
    await enforce_index_queue_capacity(db, current_session.id)

    # 2) Create the document row
    doc = Document(
        meeting_id=meeting_id,
        doc_type=payload.doc_type,
        filename=payload.filename,
        raw_text=payload.text,
        status="pending",
        error=None,
        processing_started_at=None,
        indexed_at=None,
    )
    db.add(doc)

    try:
        # Persist first so the queued job has a stable, committed document ID.
        await db.commit()
        await db.refresh(doc)

        try:
            enqueue_index_document(str(doc.id))
        except Exception as queue_exc:
            doc.status = "failed"
            doc.error = f"queue failed: {queue_exc}"[:4000]
            await db.commit()
            raise HTTPException(status_code=500, detail="failed to enqueue indexing job")

        return DocumentCreateResponse(document_id=str(doc.id), status=doc.status)
    except Exception:
        await db.rollback()
        raise


@app.post(
    "/meetings/{meeting_id}/documents/upload",
    response_model=DocumentCreateResponse | list[DocumentCreateResponse],
)
async def upload_document(
    meeting_id: uuid.UUID,
    request: Request,
    doc_type: str = Form(...),
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    filename: str | None = Form(default=None),
    upload_id: str | None = Form(default=None),
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
) -> DocumentCreateResponse | list[DocumentCreateResponse]:
    """
    Multipart upload endpoint (file-in pipeline).
    Stores the raw file, creates a pending Document row, then enqueues background processing.
    """
    await _get_owned_meeting_or_404(db, meeting_id, current_session.id)
    enforce_per_minute_limits("upload", _client_ip(request), current_session.id)
    await enforce_index_queue_capacity(db, current_session.id)

    normalized_doc_type = doc_type.strip()
    if not normalized_doc_type:
        raise HTTPException(status_code=400, detail="doc_type is required")
    if len(normalized_doc_type) > 50:
        raise HTTPException(status_code=400, detail="doc_type must be 50 characters or less")

    upload_files: list[UploadFile] = []
    if file is not None:
        upload_files.append(file)
    if files:
        upload_files.extend(files)
    if not upload_files:
        raise HTTPException(status_code=400, detail="at least one file is required")
    if MAX_FILES_PER_UPLOAD_REQUEST > 0 and len(upload_files) > MAX_FILES_PER_UPLOAD_REQUEST:
        raise HTTPException(
            status_code=413,
            detail=f"too many files in one request; max allowed is {MAX_FILES_PER_UPLOAD_REQUEST}",
        )

    responses: list[DocumentCreateResponse] = []
    for current_file in upload_files:
        await enforce_index_queue_capacity(db, current_session.id)
        try:
            # Enforce a strict file-type allowlist at the edge.
            validate_supported_upload(current_file.filename, current_file.content_type)
        except UnsupportedFormatError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc

        content = await current_file.read()
        await current_file.close()
        if not content:
            raise HTTPException(status_code=400, detail="uploaded file is empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"file too large; max allowed is {MAX_UPLOAD_BYTES} bytes",
            )
        await enforce_daily_upload_quotas(db, current_session.id, len(content))

        document_id = uuid.uuid4()
        original_filename = _normalize_upload_filename(current_file.filename)
        normalized_filename = _normalize_upload_filename(filename) if filename else original_filename
        mime_type = (current_file.content_type or "").strip() or None
        size_bytes = len(content)
        try:
            storage_path = save_upload_bytes(str(document_id), original_filename, content)
        except Exception as storage_exc:
            raise HTTPException(
                status_code=500,
                detail=f"failed to persist upload: {storage_exc}",
            ) from storage_exc

        doc = Document(
            id=document_id,
            meeting_id=meeting_id,
            doc_type=normalized_doc_type,
            filename=normalized_filename,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            raw_text="",
            status="pending",
            error=None,
            processing_started_at=None,
            indexed_at=None,
        )
        db.add(doc)

        try:
            await db.commit()
            await db.refresh(doc)

            try:
                enqueue_index_document(str(doc.id))
            except Exception as queue_exc:
                doc.status = "failed"
                doc.error = f"queue failed: {queue_exc}"[:4000]
                await db.commit()
                raise HTTPException(status_code=500, detail="failed to enqueue indexing job")

            responses.append(
                DocumentCreateResponse(
                    document_id=str(doc.id),
                    status=doc.status,
                    original_filename=original_filename,
                    upload_id=upload_id,
                )
            )
        except Exception:
            await db.rollback()
            try:
                delete_upload_object(storage_path)
            except Exception:
                logger.exception("failed to clean up uploaded file after create failure")
            raise

    if len(responses) == 1:
        return responses[0]
    return responses


@app.get("/meetings/{meeting_id}/documents", response_model=list[DocumentListItemResponse])
async def list_meeting_documents(
    meeting_id: uuid.UUID,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_meeting_or_404(db, meeting_id, current_session.id)

    docs_result = await db.execute(
        select(Document).where(Document.meeting_id == meeting_id).order_by(Document.created_at.desc())
    )
    docs = docs_result.scalars().all()
    return [
        DocumentListItemResponse(
            document_id=str(doc.id),
            meeting_id=str(doc.meeting_id),
            doc_type=doc.doc_type,
            filename=doc.filename,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            status=doc.status,
            error=doc.error,
            processing_started_at=doc.processing_started_at,
            indexed_at=doc.indexed_at,
        )
        for doc in docs
    ]


@app.post("/internal/reaper/trigger")
async def trigger_reaper(
    max_age_minutes: int | None = None,
    x_admin_token: str | None = Header(default=None),
    x_reaper_token: str | None = Header(default=None),
):
    """
    Small operational endpoint for scheduled cleanup.
    Protect with REAPER_TRIGGER_TOKEN in production.
    """
    _require_admin_token(x_admin_token)
    required_token = os.getenv("REAPER_TRIGGER_TOKEN")
    if required_token and x_reaper_token != required_token:
        raise HTTPException(status_code=401, detail={"code": "invalid_reaper_token", "message": "Invalid reaper token."})

    try:
        job_id = enqueue_reaper_job(max_age_minutes=max_age_minutes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to enqueue reaper job: {exc}") from exc

    return {"queued": True, "job_id": job_id}


@app.get("/documents/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_owned_document_or_404(db, document_id, current_session.id)
    return DocumentStatusResponse(
        document_id=str(doc.id),
        status=doc.status,
        filename=doc.filename,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        error=doc.error,
        processing_started_at=doc.processing_started_at,
        indexed_at=doc.indexed_at,
    )


@app.post("/documents/{document_id}/reindex", response_model=DocumentCreateResponse)
async def reindex_document(
    document_id: uuid.UUID,
    request: Request,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-enqueue indexing for an existing document.
    Useful for failed jobs or explicit reprocessing requests.
    """
    enforce_per_minute_limits("reindex", _client_ip(request), current_session.id)
    doc = await _get_owned_document_or_404(db, document_id, current_session.id)
    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="document is already processing")
    await enforce_index_queue_capacity(db, current_session.id)

    if REINDEX_COOLDOWN_SECONDS > 0:
        now = datetime.utcnow()
        last_event = doc.processing_started_at or doc.indexed_at or doc.created_at
        if last_event is not None:
            seconds_since = int((now - last_event.replace(tzinfo=None)).total_seconds())
            if seconds_since < REINDEX_COOLDOWN_SECONDS:
                retry_after = REINDEX_COOLDOWN_SECONDS - max(0, seconds_since)
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "reindex_cooldown",
                        "message": "Reindex was requested too recently. Please wait before retrying.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

    doc.status = "pending"
    doc.error = None
    doc.processing_started_at = None
    doc.indexed_at = None
    await db.commit()
    await db.refresh(doc)

    try:
        enqueue_index_document(str(doc.id))
    except Exception as queue_exc:
        doc.status = "failed"
        doc.error = f"queue failed: {queue_exc}"[:4000]
        await db.commit()
        raise HTTPException(status_code=500, detail="failed to enqueue indexing job")

    return DocumentCreateResponse(document_id=str(doc.id), status=doc.status)


async def _meeting_indexing_in_progress(db: AsyncSession, meeting_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(Document.id)
        .where(Document.meeting_id == meeting_id)
        .where(Document.status.in_(["pending", "processing"]))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _meeting_has_indexed_chunks(db: AsyncSession, meeting_id: uuid.UUID) -> bool:
    """
    True when at least one chunk for the meeting is already indexed.
    We use this to avoid showing "still indexing" when there is already
    searchable content and the user question is simply unsupported.
    """
    result = await db.execute(
        select(Chunk.id)
        .where(Chunk.meeting_id == meeting_id)
        .where(Chunk.embedding.is_not(None))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _load_recent_chat_turns(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    limit: int = 6,
) -> list[tuple[str, str | None]]:
    """
    Load recent chat runs (oldest -> newest) for lightweight conversational continuity.
    Each tuple is (user_question, assistant_answer_or_none).
    """
    result = await db.execute(
        select(Run)
        .where(Run.meeting_id == meeting_id)
        .where(Run.run_type == "chat")
        .order_by(Run.created_at.desc())
        .limit(limit)
    )
    runs = list(reversed(result.scalars().all()))
    turns: list[tuple[str, str | None]] = []
    for run in runs:
        user_question = (run.input_text or "").strip()
        if not user_question:
            continue
        assistant_answer: str | None = None
        if isinstance(run.response_json, dict):
            value = run.response_json.get("answer")
            if isinstance(value, str) and value.strip():
                assistant_answer = value.strip()
        turns.append((user_question, assistant_answer))
    return turns


def _format_history_for_chat_prompt(turns: list[tuple[str, str | None]]) -> str:
    lines: list[str] = []
    for user_question, assistant_answer in turns:
        lines.append(f"User: {user_question}")
        if assistant_answer:
            lines.append(f"Assistant: {assistant_answer}")
    return "\n".join(lines)


@app.post("/meetings/{meeting_id}/chat", response_model=ChatResponse)
async def chat_with_meeting(
    meeting_id: uuid.UUID,
    payload: ChatRequest,
    request: Request,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    # Capture total request latency for observability.
    t0 = time.monotonic()
    enforce_per_minute_limits("chat", _client_ip(request), current_session.id)
    await enforce_daily_run_quotas(db, current_session.id, run_type="chat")

    await _get_owned_meeting_or_404(db, meeting_id, current_session.id)

    recent_turns = await _load_recent_chat_turns(db=db, meeting_id=meeting_id, limit=6)

    # Improve follow-up questions ("what about that?") by enriching retrieval query
    # with a small amount of recent user context.
    recent_user_questions = [q for q, _ in recent_turns[-2:]]
    retrieval_question = payload.question
    if recent_user_questions:
        retrieval_question = "\n".join([*recent_user_questions, payload.question])

    query_vectors = await embed_texts([retrieval_question])
    if not query_vectors:
        raise HTTPException(status_code=500, detail="failed to embed question")

    # Retrieve relevant context chunks before generation.
    chunks = await retrieve_similar_chunks(db, meeting_id, query_vectors[0], top_k=6)
    retrieved_chunk_ids = [str(chunk.id) for chunk in chunks]
    if DEBUG_GROUNDING:
        logger.info("grounding.retrieved_chunks meeting_id=%s count=%d", meeting_id, len(chunks))
    if not chunks:
        indexing_in_progress = await _meeting_indexing_in_progress(db, meeting_id)
        has_indexed_chunks = await _meeting_has_indexed_chunks(db, meeting_id)

        # Only say "still indexing" when *no* indexed content exists yet.
        if indexing_in_progress and not has_indexed_chunks:
            response = ChatResponse(
                answer="This meeting is still being indexed. Try again in a moment.",
                citations=[],
                run_id=None,
            )
        else:
            response = ChatResponse(
                answer="I don't know based on the provided context.",
                citations=[],
                run_id=None,
            )
        try:
            # Best-effort run logging: failures must not break user-facing responses.
            run = await log_chat_run(
                db=db,
                meeting_id=meeting_id,
                question=payload.question,
                retrieved_chunk_ids=retrieved_chunk_ids,
                citations=response.model_dump()["citations"],
                response_payload=response.model_dump(),
                had_retry=False,
                invalid_reason_counts={},
                latency_ms=int((time.monotonic() - t0) * 1000),
                model=CHAT_MODEL,
                embedding_model=EMBEDDING_MODEL,
            )
            response.run_id = str(run.id)
        except Exception:
            logger.exception("failed to log chat run")
        return response

    history_text = _format_history_for_chat_prompt(recent_turns)
    model_question = payload.question
    if history_text:
        model_question = (
            "Use prior turns only when relevant for disambiguation.\n\n"
            f"CHAT HISTORY (oldest to newest):\n{history_text}\n\n"
            f"CURRENT QUESTION:\n{payload.question}"
        )

    grounded, meta = await answer_with_citations(model_question, chunks)
    response = ChatResponse(**grounded, run_id=None)

    try:
        # Persist a run row for debugging/audit: retrieval, citations, retry metadata, latency.
        run = await log_chat_run(
            db=db,
            meeting_id=meeting_id,
            question=payload.question,
            retrieved_chunk_ids=retrieved_chunk_ids,
            citations=response.model_dump()["citations"],
            response_payload=response.model_dump(),
            had_retry=bool(meta.get("had_retry", False)),
            invalid_reason_counts=dict(meta.get("invalid_reason_counts", {})),
            latency_ms=int((time.monotonic() - t0) * 1000),
            model=CHAT_MODEL,
            embedding_model=EMBEDDING_MODEL,
        )
        response.run_id = str(run.id)
    except Exception:
        logger.exception("failed to log chat run")

    return response


@app.get("/meetings/{meeting_id}/chat/history", response_model=list[ChatHistoryTurn])
async def chat_history(
    meeting_id: uuid.UUID,
    limit: int = 100,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_meeting_or_404(db, meeting_id, current_session.id)

    normalized_limit = max(1, min(limit, 300))
    result = await db.execute(
        select(Run)
        .where(Run.meeting_id == meeting_id)
        .where(Run.run_type == "chat")
        .order_by(Run.created_at.desc())
        .limit(normalized_limit)
    )
    runs = list(reversed(result.scalars().all()))

    turns: list[ChatHistoryTurn] = []
    for run in runs:
        answer: str | None = None
        citations: list[dict] = []
        if isinstance(run.response_json, dict):
            maybe_answer = run.response_json.get("answer")
            if isinstance(maybe_answer, str):
                answer = maybe_answer
            maybe_citations = run.response_json.get("citations")
            if isinstance(maybe_citations, list):
                citations = [item for item in maybe_citations if isinstance(item, dict)]
        turns.append(
            ChatHistoryTurn(
                run_id=str(run.id),
                question=run.input_text,
                answer=answer,
                citations=citations,
                created_at=run.created_at,
            )
        )
    return turns


@app.post("/meetings/{meeting_id}/chat/feedback")
async def submit_chat_feedback(
    meeting_id: uuid.UUID,
    payload: ChatFeedbackRequest,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    meeting = await _get_owned_meeting_or_404(db, meeting_id, current_session.id)

    try:
        run_id = uuid.UUID(payload.run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid run_id") from exc

    run_result = await db.execute(
        select(Run)
        .where(Run.id == run_id)
        .where(Run.meeting_id == meeting.id)
        .where(Run.run_type == "chat")
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="chat run not found")

    feedback = RunFeedback(
        run_id=run.id,
        meeting_id=meeting.id,
        session_id=current_session.id,
        verdict=payload.verdict.strip().lower(),
        reason=payload.reason,
        created_at=datetime.utcnow(),
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return {"ok": True, "feedback_id": str(feedback.id)}


@app.get("/chunks/{chunk_id}", response_model=ChunkDetailResponse)
async def get_chunk_detail(
    chunk_id: uuid.UUID,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chunk, Document, Meeting)
        .join(Document, Document.id == Chunk.document_id)
        .join(Meeting, Meeting.id == Chunk.meeting_id)
        .where(Chunk.id == chunk_id)
        .where(Meeting.session_id == current_session.id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    chunk, document, _meeting = row
    return ChunkDetailResponse(
        chunk_id=str(chunk.id),
        meeting_id=str(chunk.meeting_id),
        document_id=str(chunk.document_id),
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        document_filename=document.filename,
        document_original_filename=document.original_filename,
        document_doc_type=document.doc_type,
    )


@app.post("/meetings/{meeting_id}/verify", response_model=VerifyResponse)
async def verify_endpoint(
    meeting_id: uuid.UUID,
    request: Request,
    current_session: GuestSession = Depends(require_guest_session),
    db: AsyncSession = Depends(get_db),
):
    # Step 6.3: endpoint wrapper around verifier engine so frontend can use the feature.
    t0 = time.monotonic()
    enforce_per_minute_limits("verify", _client_ip(request), current_session.id)
    await enforce_daily_run_quotas(db, current_session.id, run_type="verify")

    await _get_owned_meeting_or_404(db, meeting_id, current_session.id)

    # Short-circuit when meeting content is not ready yet to avoid unnecessary model calls.
    indexing_in_progress = await _meeting_indexing_in_progress(db, meeting_id)
    has_indexed_chunks = await _meeting_has_indexed_chunks(db, meeting_id)
    if indexing_in_progress and not has_indexed_chunks:
        verify_response = VerifyResponse(
            structured_summary="This meeting is still being indexed. Try again in a moment.",
            decisions=[],
            action_items=[],
            open_questions=[],
            issues=[
                Issue(
                    type="missing_context",
                    description="Meeting indexing is still in progress.",
                    evidence_chunk_ids=[],
                )
            ],
            had_retry=False,
            invalid_reason_counts={},
        )
        meta = {
            "had_retry": False,
            "invalid_reason_counts": {},
            "retrieved_chunk_ids": [],
            "model": "gpt-4.1-mini",
        }
    elif not has_indexed_chunks:
        verify_response = VerifyResponse(
            structured_summary="No indexed meeting content is available to verify.",
            decisions=[],
            action_items=[],
            open_questions=[],
            issues=[
                Issue(
                    type="missing_context",
                    description="No indexed chunks found for this meeting.",
                    evidence_chunk_ids=[],
                )
            ],
            had_retry=False,
            invalid_reason_counts={},
        )
        meta = {
            "had_retry": False,
            "invalid_reason_counts": {},
            "retrieved_chunk_ids": [],
            "model": "gpt-4.1-mini",
        }
    else:
        try:
            # Step 6.3: run extraction + grounding + rule checks.
            verify_response, meta = await verify_meeting(db=db, meeting_id=meeting_id)
        except Exception:
            # Fail-safe behavior: verification errors should not surface as raw 500s.
            logger.exception("verify engine failed meeting_id=%s", meeting_id)
            verify_response = VerifyResponse(
                structured_summary="Unable to verify this meeting right now. Please try again.",
                decisions=[],
                action_items=[],
                open_questions=[],
                issues=[
                    Issue(
                        type="other",
                        description="Verifier engine failed unexpectedly.",
                        evidence_chunk_ids=[],
                    )
                ],
                had_retry=False,
                invalid_reason_counts={},
            )
            meta = {
                "had_retry": False,
                "invalid_reason_counts": {},
                "retrieved_chunk_ids": [],
                "model": "gpt-4.1-mini",
            }

    try:
        # Step 6.3: best-effort run logging (endpoint response should not fail if logging fails).
        await log_verify_run(
            db=db,
            meeting_id=meeting_id,
            retrieved_chunk_ids=list(meta.get("retrieved_chunk_ids", [])),
            verify_payload=verify_response.model_dump(),
            had_retry=bool(meta.get("had_retry", False)),
            invalid_reason_counts=dict(meta.get("invalid_reason_counts", {})),
            latency_ms=int((time.monotonic() - t0) * 1000),
            model=str(meta.get("model", "gpt-4.1-mini")),
        )
    except Exception:
        logger.exception("failed to log verify run")

    return verify_response


@app.get("/analytics/answer-quality")
async def answer_quality_analytics(
    meeting_id: uuid.UUID | None = None,
    x_admin_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Lightweight telemetry endpoint to monitor answer quality and support feedback loops.
    """
    _require_admin_token(x_admin_token)
    base_runs_stmt = (
        select(Run)
        .join(Meeting, Meeting.id == Run.meeting_id)
        .where(Run.run_type == "chat")
    )
    aggregate_stmt = (
        select(
            func.count(Run.id),
            func.avg(Run.latency_ms),
        )
        .select_from(Run)
        .join(Meeting, Meeting.id == Run.meeting_id)
        .where(Run.run_type == "chat")
    )
    feedback_stmt = (
        select(RunFeedback.verdict, func.count(RunFeedback.id))
        .join(Meeting, Meeting.id == RunFeedback.meeting_id)
        .group_by(RunFeedback.verdict)
    )
    if meeting_id:
        meeting_result = await db.execute(select(Meeting.id).where(Meeting.id == meeting_id))
        if meeting_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="meeting not found")
        base_runs_stmt = base_runs_stmt.where(Run.meeting_id == meeting_id)
        aggregate_stmt = aggregate_stmt.where(Run.meeting_id == meeting_id)
        feedback_stmt = feedback_stmt.where(RunFeedback.meeting_id == meeting_id)

    run_result = await db.execute(aggregate_stmt)
    total_runs, avg_latency_ms = run_result.one()

    feedback_result = await db.execute(feedback_stmt)
    verdict_counts = {verdict: count for verdict, count in feedback_result.all()}

    citation_result = await db.execute(base_runs_stmt)
    runs = citation_result.scalars().all()
    no_citation_count = 0
    for run in runs:
        citations = []
        if isinstance(run.response_json, dict):
            value = run.response_json.get("citations")
            if isinstance(value, list):
                citations = value
        if not citations:
            no_citation_count += 1

    return {
        "meeting_id": str(meeting_id) if meeting_id else None,
        "total_chat_runs": int(total_runs or 0),
        "avg_latency_ms": float(avg_latency_ms) if avg_latency_ms is not None else None,
        "no_citation_rate": (no_citation_count / len(runs)) if runs else 0.0,
        "feedback_counts": verdict_counts,
    }
    _require_admin_token(x_admin_token)
