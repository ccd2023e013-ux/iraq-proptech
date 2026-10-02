"""Versioned API router. Each domain contributes its own sub-router."""

from fastapi import APIRouter

from app.system.router import router as system_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system_router)
