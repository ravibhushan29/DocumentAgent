"""Document API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: UUID
    user_id: UUID
    org_id: UUID
    filename: str
    file_type: str
    status: str
    page_count: int | None
    chunk_count: int | None
    file_size_bytes: int | None
    error_msg: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    status: str
    error_msg: str | None = None
    chunk_count: int | None = None
    page_count: int | None = None
