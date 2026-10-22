"""Admin: download and manage ONNX model files."""

from collections import Counter

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.errors import bad_request, not_found
from openrecognition.app_state import AppState
from openrecognition.gallery.model_registry import (
    active_key,
    bind_active,
    build_status,
    create_custom,
    delete_custom,
    get_record,
    list_custom_specs,
    maybe_activate_download,
    removal_block_reason,
    reset_knobs,
    set_active,
    slot_for_active_key,
    update_custom,
    update_knobs,
)
from openrecognition.model_slots import CATEGORY_SLOT, SLOT_CATEGORY
from openrecognition.models.schemas import (
    ActiveModelRequest,
    CustomModelCreate,
    CustomModelCreated,
    CustomModelUpdate,
    HardwareOut,
    HardwareUpdate,
    KnobFieldOut,
    ModelActionResultOut,
    ModelCatalogEntryOut,
    ModelCategoryOut,
    ModelDownloadRequest,
    ModelDownloadResponseOut,
    ModelPresetOut,
    ModelSettingsUpdate,
    ModelsStatusOut,
    ThreadsOut,
)
from openrecognition.models_download import (
    delete_model_file,
    download_models,
)

router = APIRouter(prefix="/v1/admin/models", tags=["admin"])


def _refresh_models(state: AppState) -> None:
    bind_active(state.pool, state.db)


def _slots_to_drop(state: AppState, key: str) -> list[str]:
    slots = [key] if key in SLOT_CATEGORY else []
    slot = slot_for_active_key(state.db, key)
    if slot:
        slots.append(slot)
    for category, slot_name in CATEGORY_SLOT.items():
        if active_key(state.db, category) == key:
            slots.append(slot_name)
    return list(dict.fromkeys(slots))


def _status_out(state: AppState) -> ModelsStatusOut:
    raw = build_status(
        state.db,
        model_dir=state.settings.models_dir,
        search_dirs=state.settings.model_search_dirs,
        tier=state.hardware_info()["effective"],
        hardware=state.hardware_info(),
        threads=state.thread_info(),
        inference=state.inference_policy.status(),
        inference_backend=state.inference_policy.backend,
    )
    raw.pop("by_key", None)
    _refresh_models(state)
    return ModelsStatusOut(
        models_dir=raw["models_dir"],
        hardware=HardwareOut(**raw["hardware"]),
        threads=ThreadsOut(**raw["threads"]),
        categories=[ModelCategoryOut(**c) for c in raw["categories"]],
        presets=[ModelPresetOut(**p) for p in raw["presets"]],
        catalog=[
            ModelCatalogEntryOut(
                **{**entry, "knobs": [KnobFieldOut(**knob) for knob in entry["knobs"]]}
            )
            for entry in raw["catalog"]
        ],
        inference_backend=raw["inference_backend"],
        loaded_models=state.pool.list_models(),
        inference=raw.get("inference"),
    )


@router.get("", response_model=ModelsStatusOut)
def get_models_status(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """List models and whether each file is on disk."""
    return _status_out(state)


@router.put("/hardware", response_model=ModelsStatusOut)
def set_hardware(
    body: HardwareUpdate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Override the detected machine size. Null uses the detection again."""
    state.hardware_override = body.tier
    state.persist_runtime()
    return _status_out(state)


@router.post("/download", response_model=ModelDownloadResponseOut)
def download_models_admin(
    body: ModelDownloadRequest,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Download one or more models into the models directory."""
    model_dir = state.settings.models_dir
    try:
        results = download_models(
            model_dir,
            keys=body.keys,
            force=body.force,
            extra_specs=list_custom_specs(state.db),
        )
    except ValueError as e:
        raise bad_request("INVALID_MODEL_KEY", str(e)) from e

    counts = Counter()
    for result in results:
        record = get_record(state.db, result["key"])
        if record is not None:
            counts[record.category] += 1
    tier = state.hardware_info()["effective"]
    directories = state.settings.model_search_dirs
    for result in results:
        if result.get("status") not in ("downloaded", "skipped"):
            continue
        record = get_record(state.db, result["key"])
        if record is None:
            continue
        switched = maybe_activate_download(
            state.db,
            directories,
            result["key"],
            alone=counts[record.category] == 1,
            tier=tier,
        )
        if switched:
            result["message"] = f"{result['message']}; now in use"
        for slot in _slots_to_drop(state, result["key"]):
            state.pool.drop_session(slot)
    state.pool.load()
    _refresh_models(state)
    return ModelDownloadResponseOut(
        results=[ModelActionResultOut(**r) for r in results],
        models=state.pool.list_models(),
        inference=state.inference_policy.status(),
    )


@router.patch("/{model_key}/settings", response_model=ModelsStatusOut)
def patch_model_settings(
    model_key: str,
    body: ModelSettingsUpdate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Change knobs or ONNX fields for one model. Null clears one override."""
    try:
        update_knobs(state.db, model_key, body.overrides)
    except ValueError as e:
        msg = str(e)
        if "Unknown" in msg:
            raise not_found(msg) from e
        raise bad_request("INVALID_SETTINGS", msg) from e
    for slot in _slots_to_drop(state, model_key):
        state.pool.drop_session(slot)
    _refresh_models(state)
    return _status_out(state)


@router.post("/{model_key}/settings/reset", response_model=ModelsStatusOut)
def reset_model_settings(
    model_key: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    """Drop operator tweaks and use the shipped settings again."""
    try:
        reset_knobs(state.db, model_key)
    except ValueError as e:
        raise not_found(str(e)) from e
    for slot in _slots_to_drop(state, model_key):
        state.pool.drop_session(slot)
    _refresh_models(state)
    return _status_out(state)


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
    """Change the name, version, link, or definition of an added model."""
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
    reason = removal_block_reason(state.db, model_key)
    if reason:
        raise bad_request("MODEL_IN_USE", reason)
    record = get_record(state.db, model_key)
    slots = _slots_to_drop(state, model_key)
    try:
        delete_model_file(
            state.settings.models_dir,
            model_key,
            extra_specs=list_custom_specs(state.db),
            search_dirs=state.settings.model_search_dirs,
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
    if record is not None:
        state.pool.drop_file(record.filename)
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
    """Remove a downloaded ONNX file. The catalog entry stays."""
    reason = removal_block_reason(state.db, model_key)
    if reason:
        raise bad_request("MODEL_IN_USE", reason)
    record = get_record(state.db, model_key)
    slots = _slots_to_drop(state, model_key)
    try:
        result = delete_model_file(
            state.settings.models_dir,
            model_key,
            extra_specs=list_custom_specs(state.db),
            search_dirs=state.settings.model_search_dirs,
        )
    except ValueError as e:
        msg = str(e)
        if "Unknown" in msg:
            raise not_found(msg) from e
        raise bad_request("INVALID_MODEL_KEY", msg) from e

    for slot in slots:
        state.pool.drop_session(slot)
    if record is not None:
        state.pool.drop_file(record.filename)

    return ModelActionResultOut(**result)
