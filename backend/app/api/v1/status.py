"""GET /documents/{id}/status — poll indexing status (Section 7)."""

from __future__ import annotations

from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import DocumentNotFoundError
from app.db.session import get_db
from app.models.document import Document
from app.schemas.document import DocumentStatusResponse

router = APIRouter()


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentStatusResponse:
    """Return document status for polling (queued → processing → indexed | failed)."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.user_id,
        )
    )
    doc = result.scalars().first()
    if doc is None:
        raise DocumentNotFoundError(str(document_id))
    return DocumentStatusResponse(
        document_id=doc.id,
        status=doc.status,
        error_msg=doc.error_msg,
        chunk_count=doc.chunk_count,
        page_count=doc.page_count,
    )
