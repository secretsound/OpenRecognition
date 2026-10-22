"""Health endpoints."""

from fastapi import APIRouter, Depends

from openrecognition import __version__
from openrecognition.api.deps import get_state
from openrecognition.app_state import AppState

router = APIRouter(tags=["health"])


@router.get("/health")
def health(state: AppState = Depends(get_state)):
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
