"""Admin maintenance and config."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from openrecognition.api.deps import get_state, library_limited_ids, require_scope
from openrecognition.api.errors import bad_request
from openrecognition.app_state import AppState
from openrecognition.auth.oidc import OidcError
from openrecognition.auth.saml import fetch_idp_metadata
from openrecognition.auth.sso import check_oidc_issuer
from openrecognition.backup_bundle import build_backup, restore_backup, storage_usage
from openrecognition.logging_config import apply_runtime_logging
from openrecognition.models.schemas import (
    AppSettingsOut,
    AppSettingsPatch,
    BackupRestoreOut,
    OidcDiscoverOut,
    OidcDiscoverRequest,
    RecognitionLogListOut,
    RecognitionLogOut,
    SamlMetadataOut,
    SamlMetadataRequest,
    SelfSignedTlsOut,
    SelfSignedTlsRequest,
    ServerLogsOut,
    ServiceRestartOut,
    StorageUsageOut,
)
from openrecognition.service_restart import schedule_restart
from openrecognition.site_settings import (
    apply_settings_patch,
    server_logs_response,
    settings_response,
)
from openrecognition.tls_material import generate_self_signed

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/settings", response_model=AppSettingsOut)
def get_settings(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return settings_response(state)


@router.patch("/settings", response_model=AppSettingsOut)
def patch_settings(
    body: AppSettingsPatch,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    apply_settings_patch(state, body)
    state.persist_runtime()
    apply_runtime_logging(state.settings)
    return settings_response(state)


@router.get("/storage-usage", response_model=StorageUsageOut)
def get_storage_usage(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return StorageUsageOut(**storage_usage(state))


@router.get("/backup")
def download_backup(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    payload = build_backup(state)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="openrecognition-backup.zip"'},
    )


@router.post("/backup/restore", response_model=BackupRestoreOut)
async def upload_backup(
    file: UploadFile = File(...),
    confirm: str = Form(...),
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    if confirm != "restore":
        raise bad_request("INVALID_BACKUP", "Confirm the restore before replacing this server")
    payload = await file.read()
    try:
        restore_backup(state, payload)
    except ValueError as exc:
        raise bad_request("INVALID_BACKUP", str(exc)) from exc
    return BackupRestoreOut(message="Backup restored. Restart the server to finish applying it.")


@router.get("/server-logs", response_model=ServerLogsOut)
def server_logs(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
    lines: int = Query(200, ge=1, le=1000),
):
    return server_logs_response(state, lines)


@router.post("/tls/self-signed", response_model=SelfSignedTlsOut)
def create_self_signed(
    body: SelfSignedTlsRequest,
    _state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        created = generate_self_signed(body.hostname)
    except ValueError as exc:
        raise bad_request("INVALID_SETTINGS", str(exc)) from exc
    return SelfSignedTlsOut(**created)


@router.post("/sso/oidc/discover", response_model=OidcDiscoverOut)
def discover_oidc(
    body: OidcDiscoverRequest,
    _state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        found = check_oidc_issuer(body.issuer)
    except (OidcError, ValueError) as exc:
        raise bad_request("OIDC_DISCOVERY_FAILED", "Could not read the OpenID configuration") from exc
    return OidcDiscoverOut(**found)


@router.post("/sso/saml/metadata", response_model=SamlMetadataOut)
def load_saml_metadata(
    body: SamlMetadataRequest,
    _state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        parsed = fetch_idp_metadata(body.url)
    except ValueError as exc:
        raise bad_request("SAML_METADATA_FAILED", str(exc)) from exc
    return SamlMetadataOut(**parsed)


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
    auth=Depends(require_scope("read")),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event: str | None = Query(None, description="Filter by event, e.g. recognition.match"),
    modality: str | None = Query(None, description="Filter by modality: audio, image, video"),
    label: str | None = Query(None, description="Substring match on detected label"),
    entity_id: str | None = Query(None, description="Filter by enrollment id"),
):
    allowed = library_limited_ids(state, auth)
    items, total = state.recognition_logs.list_logs(
        limit=limit,
        offset=offset,
        event=event,
        modality=modality,
        label=label,
        entity_id=entity_id,
        entity_ids=list(allowed) if allowed is not None else None,
    )
    return RecognitionLogListOut(
        items=[RecognitionLogOut(**row) for row in items],
        total=total,
        limit=limit,
        offset=offset,
    )
