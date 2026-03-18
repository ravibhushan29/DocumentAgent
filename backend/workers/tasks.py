"""Celery task: ingest_document — runs pipeline, retry + DLQ on failure (Section 8)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from celery import Celery
from celery.exceptions import MaxRetriesExceededError

from app.services.ingestion.pipeline import run_pipeline
from app.services.queue.dlq import escalate_to_dlq

app = Celery("docagent")
app.config_from_object("workers.celeryconfig")


def _run_pipeline_sync(document_id: uuid.UUID, s3_key: str, file_type: str, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Run async pipeline from sync Celery context."""
    asyncio.run(
        run_pipeline(
            document_id=document_id,
            s3_key=s3_key,
            file_type=file_type,
            user_id=user_id,
            org_id=org_id,
        )
    )


@app.task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=5,
    default_retry_delay=30,
)
def ingest_document(
    self: Any,
    document_id: str,
    s3_key: str,
    file_type: str,
    user_id: str,
    org_id: str,
) -> None:
    """Run ingestion pipeline. Retry with exponential backoff; on max retries escalate to DLQ."""
    doc_uuid = uuid.UUID(document_id)
    user_uuid = uuid.UUID(user_id)
    org_uuid = uuid.UUID(org_id)
    try:
        _run_pipeline_sync(doc_uuid, s3_key, file_type, user_uuid, org_uuid)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(
                escalate_to_dlq(
                    document_id=doc_uuid,
                    error=str(exc),
                    payload={
                        "document_id": document_id,
                        "s3_key": s3_key,
                        "file_type": file_type,
                        "user_id": user_id,
                        "org_id": org_id,
                    },
                    retry_count=self.request.retries,
                )
            )
            raise
        delay = 2 ** (self.request.retries + 1)  # 2, 4, 8, 16, 32
        raise self.retry(exc=exc, countdown=delay)
