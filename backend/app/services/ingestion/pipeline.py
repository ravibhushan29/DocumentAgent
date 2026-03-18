"""Orchestrate parse → chunk → embed → index; emit logs + metrics (Section 7)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.core.metrics import chunks_per_document, ingestion_duration_seconds
from app.db.session import async_session_factory
from app.models.document import Document
from app.services.ingestion.chunker import chunk_pages
from app.services.ingestion.embedder import embed_chunks_async
from app.services.ingestion.indexer import bulk_upsert_chunks, mark_document_indexed
from app.services.ingestion.parser import parse_file
from app.services.storage import download_bytes

logger = structlog.get_logger(__name__)


async def run_pipeline(
    document_id: uuid.UUID,
    s3_key: str,
    file_type: str,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
) -> None:
    """
    Download → parse → chunk → embed → bulk upsert → mark indexed.
    On failure, caller (worker) should retry or DLQ.
    """
    start = time.perf_counter()
    async with async_session_factory() as session:
        # 1. Update status = processing
        await session.execute(
            text("UPDATE documents SET status = 'processing' WHERE id = :id"),
            {"id": document_id},
        )
        await session.commit()

    try:
        # 2. Download
        raw = download_bytes(s3_key)
        logger.info("pipeline.downloaded", document_id=str(document_id), size=len(raw))

        # 3. Parse
        pages = parse_file(raw, file_type)
        logger.info("pipeline.parsed", document_id=str(document_id), pages=len(pages))

        # 4. Chunk
        chunks = chunk_pages(pages)
        logger.info("pipeline.chunked", document_id=str(document_id), chunks=len(chunks))

        if not chunks:
            async with async_session_factory() as session:
                await session.execute(
                    text(
                        "UPDATE documents SET status = 'indexed', chunk_count = 0, page_count = :pc WHERE id = :id"
                    ),
                    {"id": document_id, "pc": len(pages)},
                )
                await session.commit()
            duration = time.perf_counter() - start
            ingestion_duration_seconds.labels(file_type=file_type, status="indexed").observe(duration)
            return

        # 5. Embed
        embeddings = await embed_chunks_async(chunks)
        logger.info("pipeline.embedded", document_id=str(document_id), vectors=len(embeddings))

        # 6. Index
        async with async_session_factory() as session:
            await bulk_upsert_chunks(session, document_id, user_id, org_id, chunks, embeddings)
            await mark_document_indexed(session, document_id, chunk_count=len(chunks), page_count=len(pages))

        duration = time.perf_counter() - start
        ingestion_duration_seconds.labels(file_type=file_type, status="indexed").observe(duration)
        chunks_per_document.observe(len(chunks))
        logger.info(
            "pipeline.complete",
            document_id=str(document_id),
            chunks=len(chunks),
            duration_ms=round(duration * 1000),
        )
    except Exception as e:
        duration = time.perf_counter() - start
        ingestion_duration_seconds.labels(file_type=file_type, status="failed").observe(duration)
        logger.exception("pipeline.failed", document_id=str(document_id), error=str(e))
        async with async_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE documents SET status = 'failed', error_msg = :err WHERE id = :id"
                ),
                {"id": document_id, "err": str(e)[:5000]},
            )
            await session.commit()
        raise
