"""Admin maintenance and config."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.errors import bad_request
from openrecognition.app_state import RESTART_REQUIRED_KEYS, AppState
from openrecognition.models.schemas import (
    AppSettingsOut,
    AppSettingsPatch,
    RecognitionLogListOut,
    RecognitionLogOut,
    ServiceRestartOut,
    SystemInfoOut,
)
from openrecognition.service_restart import schedule_restart
from openrecognition.system_info import collect_system_info

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _settings_out(state: AppState) -> AppSettingsOut:
    s = state.settings
    store = state._runtime_store
    return AppSettingsOut(
        maintenance_mode=state.maintenance_mode,
        enrollment_media_retention=s.enrollment_media_retention,
        inference_backend=state.inference_policy.backend,
        inference_status=state.inference_policy.status(),
        feature_flags=dict(state.feature_flags),
        default_min_confidence=state.default_min_confidence,
        default_return_unknown=state.default_return_unknown,
        default_include_sound_events=state.default_include_sound_events,
        recognition_log_retention_days=state.recognition_logs.retention_days,
        pack=s.pack,
        auth_required=s.auth_required,
        docs_enabled=s.docs_enabled,
        web_enabled=s.web_enabled,
        data_dir=str(s.data_dir),
        model_packs_dir=str(s.model_packs_dir),
        session_ttl_minutes=s.session_ttl_minutes,
        mqtt_enabled=s.mqtt_enabled,
        mqtt_host=s.mqtt_host,
        mqtt_port=s.mqtt_port,
        mqtt_topic_prefix=s.mqtt_topic_prefix,
        model_idle_unload_minutes=s.model_idle_unload_minutes,
        auth_rate_limit_per_minute=s.auth_rate_limit_per_minute,
        host=s.host,
        port=s.port,
        runtime_settings_path=str(store.path) if store else "",
        restart_required_for=list(RESTART_REQUIRED_KEYS),
        system=SystemInfoOut(
            **collect_system_info(
                host=s.host,
                port=s.port,
                web_origin=s.web_origin,
            ),
        ),
    )


@router.get("/settings", response_model=AppSettingsOut)
def get_settings(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return _settings_out(state)


@router.patch("/settings", response_model=AppSettingsOut)
def patch_settings(
    body: AppSettingsPatch,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    if body.inference_backend is not None:
        state.settings.inference_backend = body.inference_backend
        state.inference_policy.set_backend(body.inference_backend)
    if body.maintenance_mode is not None:
        state.maintenance_mode = body.maintenance_mode
    if body.enrollment_media_retention is not None:
        if body.enrollment_media_retention not in ("keep", "embeddings_only"):
            raise bad_request(
                "INVALID_RETENTION",
                "enrollment_media_retention must be 'keep' or 'embeddings_only'",
            )
        state.settings.enrollment_media_retention = body.enrollment_media_retention  # type: ignore[assignment]
    if body.feature_flags is not None:
        state.feature_flags.update(body.feature_flags)
    if body.default_min_confidence is not None:
        state.default_min_confidence = body.default_min_confidence
    if body.default_return_unknown is not None:
        state.default_return_unknown = body.default_return_unknown
    if body.default_include_sound_events is not None:
        state.default_include_sound_events = body.default_include_sound_events
    if body.recognition_log_retention_days is not None:
        state.recognition_logs.set_retention_days(body.recognition_log_retention_days)
        state.recognition_logs.prune_old()
    if body.session_ttl_minutes is not None:
        state.settings.session_ttl_minutes = body.session_ttl_minutes
        state.sessions.ttl_minutes = body.session_ttl_minutes
    if body.model_idle_unload_minutes is not None:
        state.settings.model_idle_unload_minutes = body.model_idle_unload_minutes
        state.pool.idle_unload_minutes = body.model_idle_unload_minutes
    state.persist_runtime()
    return _settings_out(state)


@router.post("/restart", response_model=ServiceRestartOut, status_code=202)
def restart_service(
    background: BackgroundTasks,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    state.persist_runtime()
    background.add_task(schedule_restart)
    return ServiceRestartOut(
        message="Service restart scheduled. The API will be briefly unavailable.",
    )


@router.post("/reload")
def reload_config(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    state.pool.load()
    return {
        "ok": True,
        "models": state.pool.list_models(),
        "inference": state.inference_policy.status(),
    }


@router.post("/maintenance")
def set_maintenance(
    enabled: bool,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    state.maintenance_mode = enabled
    state.persist_runtime()
    return {"maintenance_mode": enabled}


@router.get("/feature-flags")
def get_flags(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return state.feature_flags


@router.patch("/feature-flags")
def patch_flags(
    flags: dict[str, bool],
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    state.feature_flags.update(flags)
    state.persist_runtime()
    return state.feature_flags


@router.get("/logs", response_model=RecognitionLogListOut)
def list_recognition_logs(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event: str | None = Query(None, description="Filter by event, e.g. recognition.match"),
    modality: str | None = Query(None, description="Filter by modality: audio, image, video"),
    label: str | None = Query(None, description="Substring match on detected label"),
):
    items, total = state.recognition_logs.list_logs(
        limit=limit,
        offset=offset,
        event=event,
        modality=modality,
        label=label,
    )
    return RecognitionLogListOut(
        items=[RecognitionLogOut(**row) for row in items],
        total=total,
        limit=limit,
        offset=offset,
    )
