"""GET /documents, GET /documents/{id}, DELETE /documents/{id}."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import DocumentNotFoundError
from app.db.session import get_db
from app.models.document import Document
from app.schemas.document import DocumentOut

router = APIRouter()


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentOut]:
    """List current user's documents."""
    result = await db.execute(
        select(Document).where(Document.user_id == current_user.user_id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentOut:
    """Get one document by id. 404 if not found or not owned by user."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.user_id,
        )
    )
    doc = result.scalars().first()
    if doc is None:
        raise DocumentNotFoundError(str(document_id))
    return DocumentOut.model_validate(doc)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete document and its chunks. 404 if not found or not owned."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.user_id,
        )
    )
    doc = result.scalars().first()
    if doc is None:
        raise DocumentNotFoundError(str(document_id))
    await db.delete(doc)
    await db.commit()
