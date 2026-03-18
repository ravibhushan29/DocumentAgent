"""Unit tests for chunker (Section 18)."""

from app.services.ingestion.chunker import Chunk, chunk_pages
from app.services.ingestion.parser import PageContent


def test_chunk_pages_empty() -> None:
    assert chunk_pages([]) == []


def test_chunk_pages_single_short_page() -> None:
    pages = [PageContent(page_number=1, text="Hello world.")]
    chunks = chunk_pages(pages)
    assert len(chunks) >= 1
    assert chunks[0].content == "Hello world."
    assert chunks[0].page_number == 1
    assert chunks[0].chunk_index == 0


def test_chunk_pages_multiple_pages() -> None:
    pages = [
        PageContent(page_number=1, text="Page one. " * 50),
        PageContent(page_number=2, text="Page two. " * 50),
    ]
    chunks = chunk_pages(pages)
    assert len(chunks) >= 1
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.token_count is not None for c in chunks)
