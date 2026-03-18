"""POST /documents/upload — validate, S3 upload, DB insert, Kafka produce, return 202 (Section 7)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import DuplicateDocumentError, FileTooLargeError, UnsupportedFileTypeError
from app.core.metrics import uploads_total
from app.db.session import get_db
from app.models.document import Document
from app.schemas.upload import UploadResponse
from app.services.queue.producer import produce_ingestion_message
from app.services.storage import build_key, upload_bytes

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
EXT_MAP = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


@router.post("/documents/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> UploadResponse:
    """
    1. Validate Content-Type (PDF/DOCX)
    2. Read bytes, reject if > 500MB
    3. SHA-256 hash → dedupe check
    4. Upload to S3
    5. INSERT document (status=pending)
    6. Produce to Kafka (doc.ingestion)
    7. Return 202
    """
    from app.core.config import get_settings
    settings = get_settings()

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        uploads_total.labels(file_type=file.content_type or "unknown", status="rejected").inc()
        raise UnsupportedFileTypeError(file.content_type or "unknown")

    ext = EXT_MAP[file.content_type]
    file_type = ext

    raw = await file.read()
    if len(raw) > settings.MAX_FILE_BYTES:
        raise FileTooLargeError(len(raw), settings.MAX_FILE_BYTES)

    content_hash = hashlib.sha256(raw).hexdigest()
    s3_key = build_key(str(current_user.user_id), content_hash, ext)

    # Dedupe: same content_hash for this user
    result = await db.execute(
        select(Document.id).where(
            Document.user_id == current_user.user_id,
            Document.content_hash == content_hash,
        ).limit(1)
    )
    existing = result.scalars().first()
    if existing is not None:
        raise DuplicateDocumentError(str(existing))

    upload_bytes(s3_key, raw, content_type=file.content_type)

    doc = Document(
        user_id=current_user.user_id,
        org_id=current_user.org_id,
        filename=file.filename or "upload",
        file_type=file_type,
        s3_key=s3_key,
        content_hash=content_hash,
        status="pending",
        file_size_bytes=len(raw),
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    await produce_ingestion_message(
        document_id=doc.id,
        s3_key=s3_key,
        file_type=file_type,
        user_id=current_user.user_id,
        org_id=current_user.org_id,
    )

    # Optional: also enqueue to Celery (Redis) so Celery worker can process without Kafka consumer
    try:
        from workers.tasks import ingest_document
        ingest_document.delay(
            str(doc.id),
            s3_key,
            file_type,
            str(current_user.user_id),
            str(current_user.org_id),
        )
    except ImportError:
        pass  # Run workers/kafka_consumer.py to process from Kafka

    uploads_total.labels(file_type=file_type, status="success").inc()
    return UploadResponse(document_id=doc.id, status="queued")
