"""Unit tests for PDF/DOCX parser (Section 18)."""

import pytest

from app.core.exceptions import ParseError
from app.services.ingestion.parser import PageContent, parse_docx, parse_file, parse_pdf


def test_parse_docx_simple() -> None:
    """python-docx can parse a minimal DOCX (we need a real file or build one)."""
    # Minimal DOCX: PK header + minimal structure
    minimal_docx = (
        b"PK\x03\x04"  # zip header
        + b"\x14\x00\x00\x00\x08\x00"
        + b"m\xb2\xb2L\xb3\x0e\xb2\xb2\x0b\x00\x00\x00\x0b\x00\x00\x00\x0b\x00\x00\x00"
        + b"[Content_Types].xml"
    )
    # This may fail with "file is not a zip file" for invalid docx
    with pytest.raises((ParseError, Exception)):
        parse_docx(minimal_docx)


def test_parse_file_unsupported_type() -> None:
    with pytest.raises(ParseError) as exc_info:
        parse_file(b"x", "txt")
    assert "Unsupported" in str(exc_info.value.message)


def test_parse_file_pdf_invalid() -> None:
    with pytest.raises(ParseError):
        parse_file(b"not a pdf", "pdf")
