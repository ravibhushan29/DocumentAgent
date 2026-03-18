from fastapi import APIRouter

from app.api.v1 import auth, documents, health, status, upload

api_router = APIRouter(prefix="/api/v1", tags=["v1"])
api_router.include_router(health.router, prefix="")
api_router.include_router(auth.router, prefix="")
api_router.include_router(upload.router, prefix="")
api_router.include_router(documents.router, prefix="")
api_router.include_router(status.router, prefix="")
