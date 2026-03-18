"""Liveness and readiness endpoints (K8s probes)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 if process is up."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness probe — returns 200 if DB (and optionally Redis) are reachable."""
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
