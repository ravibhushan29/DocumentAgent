"""aiokafka producer: acks=all, idempotent, partition key = user_id (Section 8)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import get_settings
from app.core.exceptions import QueuePublishError
from app.core.logging import get_logger
from app.core.metrics import kafka_messages_produced_total

logger = get_logger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    """Get or create singleton producer."""
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await _producer.start()
    return _producer


async def produce_ingestion_message(
    document_id: uuid.UUID,
    s3_key: str,
    file_type: str,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
) -> None:
    """Produce to doc.ingestion with key=user_id for partition ordering."""
    settings = get_settings()
    payload = {
        "document_id": str(document_id),
        "s3_key": s3_key,
        "file_type": file_type,
        "user_id": str(user_id),
        "org_id": str(org_id),
    }
    try:
        producer = await get_producer()
        await producer.send_and_wait(
            settings.KAFKA_TOPIC_INGESTION,
            value=payload,
            key=str(user_id),
        )
        kafka_messages_produced_total.inc()
        logger.info("kafka.produced", document_id=str(document_id), topic=settings.KAFKA_TOPIC_INGESTION)
    except KafkaError as e:
        logger.exception("kafka.produce_error", document_id=str(document_id), error=str(e))
        raise QueuePublishError(str(e)) from e


async def close_producer() -> None:
    """Shutdown producer (e.g. on app shutdown)."""
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
