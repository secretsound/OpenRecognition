"""Health endpoints."""

from fastapi import APIRouter, Depends, Request

from openrecognition import __version__
from openrecognition.api.deps import get_state, require_reader
from openrecognition.app_state import AppState

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request, state: AppState = Depends(get_state)):
    if not state.settings.health_detail_public:
        require_reader(request, state)
    docs = {}
    if state.settings.docs_enabled:
        docs = {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "docs_portal": "/api",
        }
    return {
        "status": "ok",
        "version": __version__,
        "hardware": state.hardware_info(),
        "models": state.pool.list_models(),
        "inference": state.inference_policy.status(),
        "maintenance": state.maintenance_mode,
        "documentation": docs,
    }


@router.get("/health/live")
def health_live():
    return {"status": "alive"}


@router.get("/health/ready")
def health_ready(state: AppState = Depends(get_state)):
    ready = state.pool.models_loaded
    return {"status": "ready" if ready else "loading", "models_loaded": ready}
