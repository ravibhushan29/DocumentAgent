from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter(prefix="/api/v1", tags=["v1"])
api_router.include_router(health.router, prefix="", include_in_schema=True)
