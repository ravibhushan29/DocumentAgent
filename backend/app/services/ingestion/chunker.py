"""RecursiveCharacterTextSplitter with overlap (Section 7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.ingestion.parser import PageContent

# Defaults from plan: 512 tokens, 64 overlap (approximate with chars: ~4 chars/token)
CHUNK_SIZE = 2048  # ~512 tokens
CHUNK_OVERLAP = 256  # ~64 tokens
SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " "]


@dataclass
class Chunk:
    """One chunk with metadata for indexing."""

    chunk_index: int
    content: str
    page_number: int | None
    token_count: int | None
    metadata: dict[str, Any] | None = None


def _split_text(text: str, chunk_size: int, overlap: int, separators: list[str]) -> list[str]:
    """Split text by separators with overlap. Simple implementation."""
    if not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        segment = text[start:end]
        if end < len(text):
            # Try to break at separator
            best = -1
            for sep in separators:
                idx = segment.rfind(sep)
                if idx > best:
                    best = idx
            if best >= 0:
                segment = segment[: best + len(separators[0]) if segment.rfind(separators[0]) == best else best + 1]
                end = start + len(segment)
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else len(text)
    return [c for c in chunks if c]


def chunk_pages(pages: list[PageContent]) -> list[Chunk]:
    """Chunk pages with RecursiveCharacterTextSplitter semantics (separators, overlap)."""
    result: list[Chunk] = []
    idx = 0
    for page in pages:
        parts = _split_text(
            page.text,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            separators=SEPARATORS,
        )
        for part in parts:
            if not part:
                continue
            # Approximate token count (~4 chars per token)
            token_count = (len(part) + 3) // 4
            result.append(
                Chunk(
                    chunk_index=idx,
                    content=part,
                    page_number=page.page_number,
                    token_count=token_count,
                    metadata=page.metadata,
                )
            )
            idx += 1
    return result
