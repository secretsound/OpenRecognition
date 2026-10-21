"""Admin: download and manage ONNX model files."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.errors import bad_request, not_found
from openrecognition.app_state import AppState
from openrecognition.gallery.custom_models import (
    active_map,
    apply_overrides,
    create_custom,
    delete_custom,
    list_custom_specs,
    set_active,
    update_custom,
)
from openrecognition.gallery.recommendations import list_recommendations, sync_pack_recommendations
from openrecognition.model_slots import CATEGORY_SLOT, SLOT_CATEGORY
from openrecognition.models.schemas import (
    ActiveModelRequest,
    CustomModelCreate,
    CustomModelCreated,
    CustomModelUpdate,
    ModelActionResultOut,
    ModelCatalogEntryOut,
    ModelCategoryOut,
    ModelDownloadRequest,
    ModelDownloadResponseOut,
    ModelPresetOut,
    ModelRecommendationOut,
    ModelsStatusOut,
)
from openrecognition.models_download import (
    delete_model_file,
    download_models,
    models_status,
)

router = APIRouter(prefix="/v1/admin/models", tags=["admin"])


def _refresh_models(state: AppState) -> None:
    apply_overrides(state.pool, state.db)


def _slots_to_drop(state: AppState, key: str) -> list[str]:
    slots = [key] if key in SLOT_CATEGORY else []
    for category, active_key in active_map(state.db).items():
        if active_key == key:
            slots.append(CATEGORY_SLOT[category])
    return list(dict.fromkeys(slots))


def _status_out(state: AppState) -> ModelsStatusOut:
    pack_dir = state.settings.pack_dir
    sync_pack_recommendations(state.db, state.settings.model_packs_dir)
    _refresh_models(state)
    raw = models_status(
        pack_dir,
        inference=state.inference_policy.status(),
        extra_specs=list_custom_specs(state.db),
        active=active_map(state.db),
    )
    return ModelsStatusOut(
        pack=raw["pack"],
        pack_dir=raw["pack_dir"],
        categories=[ModelCategoryOut(**c) for c in raw["categories"]],
        presets=[ModelPresetOut(**p) for p in raw["presets"]],
        recommendations=[ModelRecommendationOut(**r) for r in list_recommendations(state.db)],
        catalog=[ModelCatalogEntryOut(**e) for e in raw["catalog"]],
        inference_backend=state.inference_policy.backend,
        loaded_models=state.pool.list_models(),
        inference=raw.get("inference"),
    )


@router.get("", response_model=ModelsStatusOut)
def get_models_status(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """List catalog entries and whether each ONNX file exists on disk."""
    return _status_out(state)


@router.post("/download", response_model=ModelDownloadResponseOut)
def download_models_admin(
    body: ModelDownloadRequest,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Download one or more models into the active pack directory."""
    pack_dir = state.settings.pack_dir
    try:
        results = download_models(
            pack_dir,
            keys=body.keys,
            force=body.force,
            extra_specs=list_custom_specs(state.db),
        )
    except ValueError as e:
        raise bad_request("INVALID_MODEL_KEY", str(e)) from e

    state.pool.load()
    return ModelDownloadResponseOut(
        results=[ModelActionResultOut(**r) for r in results],
        models=state.pool.list_models(),
        inference=state.inference_policy.status(),
    )


@router.post("/custom", response_model=CustomModelCreated)
def create_custom_model(
    body: CustomModelCreate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Add a downloadable model for an existing category."""
    try:
        spec = create_custom(
            state.db,
            label=body.label,
            category=body.category,
            version=body.version,
            url=body.url,
            onnx=body.onnx,
        )
    except ValueError as e:
        raise bad_request("INVALID_MODEL", str(e)) from e
    return CustomModelCreated(key=spec.key)


@router.patch("/custom/{model_key}", response_model=CustomModelCreated)
def update_custom_model(
    model_key: str,
    body: CustomModelUpdate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Change the name, version, link, or run settings of an added model."""
    try:
        spec = update_custom(
            state.db,
            model_key,
            label=body.label,
            version=body.version,
            url=body.url,
            onnx=body.onnx,
        )
    except ValueError as e:
        msg = str(e)
        if "Unknown" in msg:
            raise not_found(msg) from e
        raise bad_request("INVALID_MODEL", msg) from e
    for slot in _slots_to_drop(state, model_key):
        state.pool.drop_session(slot)
    _refresh_models(state)
    return CustomModelCreated(key=spec.key)


@router.delete("/custom/{model_key}", response_model=ModelActionResultOut)
def delete_custom_model(
    model_key: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Remove an added model from the list and delete its file."""
    slots = _slots_to_drop(state, model_key)
    try:
        delete_model_file(
            state.settings.pack_dir,
            model_key,
            extra_specs=list_custom_specs(state.db),
        )
    except ValueError as e:
        msg = str(e)
        if "Unknown" not in msg:
            raise bad_request("INVALID_MODEL_KEY", msg) from e
    try:
        delete_custom(state.db, model_key)
    except ValueError as e:
        raise not_found(str(e)) from e
    for slot in slots:
        state.pool.drop_session(slot)
    _refresh_models(state)
    return ModelActionResultOut(key=model_key, status="deleted", message="Removed from the list")


@router.post("/active", response_model=ModelActionResultOut)
def activate_model(
    body: ActiveModelRequest,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Use this model for its category."""
    try:
        slot = set_active(state.db, body.category, body.key)
    except ValueError as e:
        raise bad_request("INVALID_MODEL", str(e)) from e
    state.pool.drop_session(slot)
    _refresh_models(state)
    return ModelActionResultOut(key=body.key, status="active", message="This model is now in use")


@router.delete("/{model_key}", response_model=ModelActionResultOut)
def delete_model_admin(
    model_key: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Remove a downloaded ONNX file from disk (does not uninstall the catalog entry)."""
    slots = _slots_to_drop(state, model_key)
    try:
        result = delete_model_file(
            state.settings.pack_dir,
            model_key,
            extra_specs=list_custom_specs(state.db),
        )
    except ValueError as e:
        msg = str(e)
        if "Unknown" in msg:
            raise not_found(msg) from e
        raise bad_request("INVALID_MODEL_KEY", msg) from e

    for slot in slots:
        state.pool.drop_session(slot)

    return ModelActionResultOut(**result)
