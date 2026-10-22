"""Prometheus-style metrics."""

from fastapi import APIRouter, Depends, Response

from openrecognition.api.deps import get_state, require_scope
from openrecognition.app_state import AppState

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    lines = [
        "# HELP openrecognition_info Service info",
        "openrecognition_info 1",
        f'openrecognition_hardware{{tier="{state.hardware_info()["effective"]}"}} 1',
        f"openrecognition_models_loaded {1 if state.pool.models_loaded else 0}",
        f"openrecognition_enrollments {len(state.gallery.list_enrollments())}",
        f"openrecognition_maintenance {1 if state.maintenance_mode else 0}",
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
