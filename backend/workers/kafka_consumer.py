"""Consume from doc.ingestion and run pipeline for each message (Section 8)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid

# Add backend to path when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from app.core.config import get_settings
from app.services.ingestion.pipeline import run_pipeline
from app.services.queue.dlq import escalate_to_dlq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAYS = [2, 4, 8, 16, 32]  # seconds


async def process_message(payload: dict) -> None:
    document_id = uuid.UUID(payload["document_id"])
    s3_key = payload["s3_key"]
    file_type = payload["file_type"]
    user_id = uuid.UUID(payload["user_id"])
    org_id = uuid.UUID(payload["org_id"])
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            await run_pipeline(document_id, s3_key, file_type, user_id, org_id)
            return
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning("pipeline.retry", document_id=str(document_id), attempt=attempt + 1, delay=delay)
                await asyncio.sleep(delay)
    if last_error:
        await escalate_to_dlq(
            document_id=document_id,
            error=str(last_error),
            payload=payload,
            retry_count=MAX_RETRIES,
        )


async def run_consumer() -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_INGESTION,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=settings.KAFKA_CONSUMER_GROUP,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                await process_message(msg.value)
                await consumer.commit()
            except Exception as e:
                logger.exception("consumer.error", error=str(e))
                # Don't commit so message is redelivered
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
