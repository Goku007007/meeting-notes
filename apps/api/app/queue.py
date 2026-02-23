import os
from typing import Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
INDEX_JOB_TIMEOUT_SECONDS = int(os.getenv("INDEX_JOB_TIMEOUT_SECONDS", "900"))
INDEX_JOB_RETRY_MAX = int(os.getenv("INDEX_JOB_RETRY_MAX", "3"))
INDEX_JOB_RETRY_INTERVALS = os.getenv("INDEX_JOB_RETRY_INTERVALS", "30,120,300")
_queue: Any = None


def get_queue() -> Any:
    """
    Single source of truth for Redis queue configuration.
    Both API endpoints and worker can reuse this.
    """
    # Import lazily so test/runtime can import app modules even when
    # redis/rq are not installed yet.
    try:
        from redis import Redis
        from rq import Queue
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RQ/Redis dependencies missing; install redis/rq."
        ) from exc

    global _queue
    if _queue is None:
        redis_conn = Redis.from_url(REDIS_URL)
        _queue = Queue("default", connection=redis_conn)
    return _queue


def _parse_retry_intervals(max_retries: int) -> int | list[int]:
    """
    Parse backoff intervals from env.
    Returns either:
    - single int seconds
    - list[int] for per-retry backoff
    """
    raw_values = [p.strip() for p in INDEX_JOB_RETRY_INTERVALS.split(",") if p.strip()]
    values: list[int] = []
    for raw in raw_values:
        try:
            value = int(raw)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    if not values:
        return 60
    if len(values) == 1:
        return values[0]
    return values[:max_retries]


def enqueue_index_document(document_id: str) -> str:
    """
    Enqueue indexing with production-safe defaults:
    - dedupe by stable job_id per document
    - timeout to avoid stuck jobs
    - retry with backoff for transient failures
    """
    try:
        from rq import Retry
        from rq.exceptions import DuplicateJobError
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RQ/Redis dependencies missing; install redis/rq."
        ) from exc

    queue = get_queue()
    job_id = f"index-document:{document_id}"
    retry = Retry(max=INDEX_JOB_RETRY_MAX, interval=_parse_retry_intervals(INDEX_JOB_RETRY_MAX))

    try:
        job = queue.enqueue(
            "app.jobs.indexing.index_document",
            document_id,
            job_id=job_id,
            job_timeout=INDEX_JOB_TIMEOUT_SECONDS,
            retry=retry,
        )
        return str(job.id)
    except DuplicateJobError:
        # Duplicate enqueue should be idempotent.
        return job_id


def enqueue_reaper_job(max_age_minutes: int | None = None) -> str:
    """
    Enqueue stale-processing cleanup. Designed for cron/scheduler triggers.
    Uses a stable job ID to avoid piling up duplicate cleanup jobs.
    """
    try:
        from rq.exceptions import DuplicateJobError
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RQ/Redis dependencies missing; install redis/rq."
        ) from exc

    queue = get_queue()
    job_id = "reap-stale-processing-documents"
    try:
        job = queue.enqueue(
            "app.jobs.indexing.reap_stale_processing_documents",
            max_age_minutes,
            job_id=job_id,
            job_timeout=120,
        )
        return str(job.id)
    except DuplicateJobError:
        return job_id
