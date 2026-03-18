"""POST /auth/register, POST /auth/login."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.organisation import Organisation
from app.models.user import User
from app.schemas.user import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter()


def _slugify(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower()).strip("-") or "org"


@router.post("/auth/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Create org and user, return JWT."""
    slug = _slugify(body.org_name)
    org = Organisation(name=body.org_name, slug=slug)
    db.add(org)
    await db.flush()
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        org_id=org.id,
        role="member",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id, org.id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, org_id=user.org_id, role=user.role, is_active=user.is_active),
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Return JWT if email/password valid."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationError("Account disabled")
    token = create_access_token(user.id, user.org_id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, email=user.email, org_id=user.org_id, role=user.role, is_active=user.is_active),
    )
