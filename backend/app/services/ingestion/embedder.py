"""Async batched OpenAI embeddings + retry (Section 7)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with OpenAI text-embedding-3-large. Retry on rate limit."""
    if not texts:
        return []
    settings = get_settings()
    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise EmbeddingError(f"openai not installed: {e}") from e

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    batch_size = settings.EMBEDDING_BATCH_SIZE
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for attempt in range(5):
            try:
                resp = await client.embeddings.create(
                    model=settings.EMBEDDING_MODEL,
                    input=batch,
                )
                for item in resp.data:
                    all_embeddings.append(item.embedding)
                break
            except Exception as e:
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str:
                    delay = 2 ** attempt
                    logger.warning("embedding_rate_limit", attempt=attempt, delay=delay)
                    await asyncio.sleep(delay)
                else:
                    raise EmbeddingError(str(e)) from e
        else:
            raise EmbeddingError("Rate limit retries exhausted")
    return all_embeddings


async def embed_chunks_async(chunks: list[Any]) -> list[list[float]]:
    """Embed a list of Chunk objects (use .content). Runs in one batch or batched by EMBEDDING_BATCH_SIZE."""
    texts = [c.content for c in chunks]
    return await embed_batch(texts)


def embed_chunks_sync(chunks: list[Any]) -> list[list[float]]:
    """Synchronous wrapper for use from Celery worker."""
    return asyncio.run(embed_chunks_async(chunks))
