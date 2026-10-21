"""Presence / last-seen."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.app_state import AppState
from openrecognition.models.schemas import PresenceEntry

router = APIRouter(prefix="/v1", tags=["presence"])


@router.get("/presence", response_model=list[PresenceEntry])
def get_presence(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    rows = state.gallery.list_presence()
    return [
        PresenceEntry(
            enrollment_id=r["enrollment_id"],
            label=r["label"],
            type=r["type"],
            last_seen_at=r["last_seen_at"],
            last_modality=r["last_modality"],
            last_camera_id=r.get("last_camera_id"),
            confidence=r.get("confidence"),
        )
        for r in rows
    ]
