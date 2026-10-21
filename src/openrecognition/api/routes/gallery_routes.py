"""Gallery export/import."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.app_state import AppState
from openrecognition.models.schemas import GalleryExportOut

router = APIRouter(prefix="/v1/gallery", tags=["gallery"])


@router.post("/export", response_model=GalleryExportOut)
def export_gallery(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    data = state.gallery.export_gallery()
    return GalleryExportOut(
        version=data["version"],
        exported_at=data["exported_at"],
        enrollment_count=data["enrollment_count"],
        data=data,
    )


@router.post("/import")
def import_gallery(
    body: dict,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    payload = body.get("data", body)
    if "enrollments" not in payload and "data" in body:
        payload = body["data"]
    count = state.gallery.import_gallery(payload)
    return {"imported": count}
