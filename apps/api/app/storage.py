from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from typing import Iterator


UPLOADS_ROOT = Path(
    os.getenv("UPLOADS_DIR", str(Path(__file__).resolve().parents[2] / "uploads"))
)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_PREFIX = os.getenv("S3_PREFIX", "meeting-notes").strip().strip("/")


def _sanitize_filename(value: str | None) -> str:
    return Path(value or "upload.bin").name or "upload.bin"


def save_upload_bytes(document_id: str, original_filename: str | None, content: bytes) -> str:
    filename = _sanitize_filename(original_filename)
    if STORAGE_BACKEND == "s3":
        return _save_upload_bytes_s3(document_id, filename, content)
    return _save_upload_bytes_local(document_id, filename, content)


def delete_upload_object(storage_path: str) -> None:
    if storage_path.startswith("s3://"):
        _delete_s3_object(storage_path)
        return
    path = Path(storage_path)
    if path.exists():
        path.unlink()
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


def _save_upload_bytes_local(document_id: str, filename: str, content: bytes) -> str:
    doc_dir = UPLOADS_ROOT / document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    path = doc_dir / filename
    path.write_bytes(content)
    return str(path)


def _save_upload_bytes_s3(document_id: str, filename: str, content: bytes) -> str:
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
    try:
        import boto3
    except ModuleNotFoundError as exc:
        raise RuntimeError("boto3 is required for STORAGE_BACKEND=s3") from exc

    key = "/".join(part for part in [S3_PREFIX, document_id, filename] if part)
    boto3.client("s3").put_object(Bucket=S3_BUCKET, Key=key, Body=content)
    return f"s3://{S3_BUCKET}/{key}"


def _delete_s3_object(storage_path: str) -> None:
    if not storage_path.startswith("s3://"):
        return
    stripped = storage_path.removeprefix("s3://")
    bucket, _, key = stripped.partition("/")
    if not bucket or not key:
        return
    try:
        import boto3
    except ModuleNotFoundError:
        return
    boto3.client("s3").delete_object(Bucket=bucket, Key=key)


@contextmanager
def materialize_storage_path(storage_path: str) -> Iterator[str]:
    if storage_path.startswith("s3://"):
        yield from _materialize_s3_path(storage_path)
        return
    yield storage_path


@contextmanager
def _materialize_s3_path(storage_path: str) -> Iterator[str]:
    try:
        import boto3
    except ModuleNotFoundError as exc:
        raise RuntimeError("boto3 is required for STORAGE_BACKEND=s3") from exc

    stripped = storage_path.removeprefix("s3://")
    bucket, _, key = stripped.partition("/")
    if not bucket or not key:
        raise RuntimeError(f"invalid s3 storage path: {storage_path}")

    filename = Path(key).name or "upload.bin"
    with tempfile.TemporaryDirectory(prefix="meeting-notes-") as temp_dir:
        local_path = Path(temp_dir) / filename
        boto3.client("s3").download_file(bucket, key, str(local_path))
        yield str(local_path)
