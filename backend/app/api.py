"""Versioned API router. Each domain contributes its own sub-router."""

from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.core.config import Settings
from app.rbac.router import router as rbac_router
from app.system.dev_router import router as dev_router
from app.system.router import router as system_router
from app.users.router import router as users_router


def build_api_router(settings: Settings) -> APIRouter:
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(system_router)
    api_router.include_router(auth_router)
    api_router.include_router(users_router)
    api_router.include_router(rbac_router)
    if settings.dev_tools:
        api_router.include_router(dev_router)
    return api_router
