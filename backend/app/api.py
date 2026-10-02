"""Versioned API router. Each domain contributes its own sub-router."""

from fastapi import APIRouter

from app.agencies.router import router as agencies_router
from app.ai.router import router as ai_router
from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.billing.router import router as billing_router
from app.core.config import Settings
from app.crm.router import router as crm_router
from app.favorites import router as favorites_router
from app.geo.manage import router as gis_router
from app.geo.pois import router as pois_router
from app.geo.router import router as geo_router
from app.map.router import router as map_router
from app.moderation.router import router as moderation_router
from app.money import router as money_router
from app.notifications.router import router as notifications_router
from app.properties.compare import router as compare_router
from app.properties.router import router as properties_router
from app.rbac.router import router as rbac_router
from app.search.router import router as search_router
from app.search.saved import router as saved_search_router
from app.system.dev_router import router as dev_router
from app.system.jobs_router import router as jobs_router
from app.system.router import router as system_router
from app.users.router import router as users_router


def build_api_router(settings: Settings) -> APIRouter:
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(system_router)
    api_router.include_router(auth_router)
    api_router.include_router(users_router)
    api_router.include_router(rbac_router)
    api_router.include_router(geo_router)
    api_router.include_router(gis_router)
    api_router.include_router(agencies_router)
    # Before the properties router: '/properties/compare' must not match '/properties/{id}'.
    api_router.include_router(compare_router)
    api_router.include_router(billing_router)  # before /properties/{id}
    api_router.include_router(properties_router)
    api_router.include_router(search_router)
    api_router.include_router(favorites_router)
    api_router.include_router(map_router)
    api_router.include_router(saved_search_router)
    api_router.include_router(pois_router)
    api_router.include_router(money_router)
    api_router.include_router(crm_router)
    api_router.include_router(ai_router)
    api_router.include_router(moderation_router)
    api_router.include_router(notifications_router)
    api_router.include_router(analytics_router)
    api_router.include_router(jobs_router)
    if settings.dev_tools:
        api_router.include_router(dev_router)
    return api_router
