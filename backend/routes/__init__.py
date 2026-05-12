"""Route aggregation — central registry of all per-feature APIRouters."""
from fastapi import APIRouter
from .auth import router as auth_router
from .series import router as series_router
from .library import router as library_router
from .calendar_routes import router as calendar_router
from .push import router as push_router
from .streaming import router as streaming_router
from .billing import router as billing_router
from .ai import router as ai_router
from .imports import router as imports_router


api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(series_router)
api_router.include_router(library_router)
api_router.include_router(calendar_router)
api_router.include_router(push_router)
api_router.include_router(streaming_router)
api_router.include_router(billing_router)
api_router.include_router(ai_router)
api_router.include_router(imports_router)


@api_router.get("/")
async def root():
    return {"app": "SeriesTrack", "version": "1.0.0"}
