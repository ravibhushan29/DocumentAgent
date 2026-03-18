"""DLQ escalation: publish to DLQ topic + update document status=failed (Section 8)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from aiokafka import AIOKafkaProducer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import dlq_events_total
from app.db.session import async_session_factory

logger = get_logger(__name__)


async def escalate_to_dlq(
    document_id: uuid.UUID,
    error: str,
    payload: dict[str, Any],
    retry_count: int,
) -> None:
    """Publish to doc.ingestion.dlq and set document status=failed."""
    settings = get_settings()
    dlq_payload = {
        "document_id": str(document_id),
        "error": error,
        "payload": payload,
        "retry_count": retry_count,
    }
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await producer.start()
        await producer.send_and_wait(settings.KAFKA_TOPIC_DLQ, value=dlq_payload, key=str(document_id))
        await producer.stop()
        dlq_events_total.labels(reason="ingestion_failed").inc()
        logger.warning("pipeline.dlq_escalated", document_id=str(document_id), error=error)
    except Exception as e:
        logger.exception("dlq.publish_failed", document_id=str(document_id), error=str(e))

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE documents SET status = 'failed', error_msg = :err WHERE id = :id"),
            {"id": document_id, "err": error[:5000]},
        )
        await session.commit()
