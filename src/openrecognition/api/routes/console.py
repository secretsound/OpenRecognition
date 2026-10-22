"""Console aggregation endpoints."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.routes.enrollments import _to_out
from openrecognition.app_state import AppState
from openrecognition.models.schemas import (
    ConsoleOverviewOut,
    PresenceEntry,
    RecognitionLogOut,
)
router = APIRouter(prefix="/v1/console", tags=["console"])


def _needs_attention(en) -> bool:
    if not en.enabled:
        return False
    if en.sample_count <= 0:
        return True
    return not (en.quality and en.quality.usable)


def _presence_entry(row: dict) -> PresenceEntry:
    return PresenceEntry(
        enrollment_id=row["enrollment_id"],
        label=row["label"],
        type=row["type"],
        last_seen_at=row["last_seen_at"],
        last_modality=row["last_modality"],
        last_camera_id=row.get("last_camera_id"),
        confidence=row.get("confidence"),
    )


@router.get("/overview", response_model=ConsoleOverviewOut)
def console_overview(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    rows = state.gallery.list_enrollments()
    quality = state.gallery.evaluate_many(rows)
    seen = state.gallery.presence_map()
    enrollments = [
        _to_out(e, quality.get(e["id"]), last_seen=seen.get(e["id"])) for e in rows
    ]
    attention = [e for e in enrollments if _needs_attention(e)][:6]
    ready_count = sum(1 for e in enrollments if e.enabled and e.quality and e.quality.usable)

    items, _total = state.recognition_logs.list_logs(limit=8, offset=0)
    recent = [RecognitionLogOut(**row) for row in items]
    has_recognition = state.recognition_logs.has_recognition()

    presence_rows = state.gallery.list_presence()
    last_seen = _presence_entry(presence_rows[0]) if presence_rows else None

    models = state.pool.list_models()
    models_ready = "heuristic" not in models or len(models) > 1

    return ConsoleOverviewOut(
        enrollments=enrollments,
        ready_count=ready_count,
        attention=attention,
        recent_activity=recent,
        last_seen=last_seen,
        models_ready=models_ready,
        wyoming_enabled=bool(state.settings.wyoming_enabled),
        webhook_count=len(state.webhooks.list_all()),
        has_recognition=has_recognition,
        hardware=state.hardware_info()["effective"],
        models=models,
    )
