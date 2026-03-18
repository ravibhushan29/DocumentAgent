"""FastAPI dependencies: auth, DB session."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token

security = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> CurrentUser:
    """Require valid JWT; return CurrentUser or raise 401."""
    if not credentials or credentials.scheme != "Bearer":
        raise AuthenticationError("Missing or invalid authorization header")
    payload = decode_access_token(credentials.credentials)
    sub = payload.get("sub")
    org_id = payload.get("org_id")
    role = payload.get("role", "member")
    if not sub or not org_id:
        raise AuthenticationError("Invalid token payload")
    return CurrentUser(
        user_id=uuid.UUID(sub),
        org_id=uuid.UUID(org_id),
        role=role,
    )
