"""Bulk upsert to pgvector + mark document indexed (Section 7)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk, EMBEDDING_DIM
from app.services.ingestion.chunker import Chunk

BATCH_SIZE = 500


async def bulk_upsert_chunks(
    session: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> None:
    """Insert chunks with ON CONFLICT DO NOTHING. Batch size 500."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")
    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i : i + BATCH_SIZE]
        batch_embeddings = embeddings[i : i + BATCH_SIZE]
        values = [
            {
                "document_id": document_id,
                "user_id": user_id,
                "org_id": org_id,
                "chunk_index": ch.chunk_index,
                "content": ch.content,
                "token_count": ch.token_count,
                "page_number": ch.page_number,
                "embedding": emb if len(emb) == EMBEDDING_DIM else None,
                "metadata": ch.metadata,
            }
            for ch, emb in zip(batch_chunks, batch_embeddings)
        ]
        stmt = insert(DocumentChunk).values(values).on_conflict_do_nothing(
            index_elements=["document_id", "chunk_index"]
        )
        await session.execute(stmt)
        await session.flush()
    await session.commit()


async def mark_document_indexed(
    session: AsyncSession,
    document_id: uuid.UUID,
    chunk_count: int,
    page_count: int,
) -> None:
    """UPDATE documents SET status=indexed, chunk_count, page_count."""
    await session.execute(
        text(
            "UPDATE documents SET status = 'indexed', chunk_count = :chunk_count, page_count = :page_count "
            "WHERE id = :document_id"
        ),
        {"document_id": document_id, "chunk_count": chunk_count, "page_count": page_count},
    )
    await session.commit()
