"""Capabilities discovery."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.app_state import AppState
from openrecognition.models.schemas import CapabilitiesOut

router = APIRouter(prefix="/v1", tags=["capabilities"])


@router.get("/capabilities", response_model=CapabilitiesOut)
def capabilities(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    c = state.capabilities()
    return CapabilitiesOut(**c)
