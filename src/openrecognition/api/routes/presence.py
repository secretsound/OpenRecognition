"""Presence / last-seen."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, library_limited_ids, require_scope
from openrecognition.app_state import AppState
from openrecognition.models.schemas import PresenceEntry

router = APIRouter(prefix="/v1", tags=["presence"])


@router.get("/presence", response_model=list[PresenceEntry])
def get_presence(
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("read")),
):
    rows = state.gallery.list_presence()
    allowed = library_limited_ids(state, auth)
    if allowed is not None:
        rows = [r for r in rows if r["enrollment_id"] in allowed]
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
