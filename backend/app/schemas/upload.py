"""Upload request/response schemas (Section 7)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """HTTP 202 response after enqueueing ingestion."""

    document_id: UUID
    status: str = Field(description="queued")
    message: str | None = Field(default=None, description="Optional message")
