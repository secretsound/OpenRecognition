"""Group CRUD and membership."""

from fastapi import APIRouter, Depends

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.errors import bad_request, not_found
from openrecognition.app_state import AppState
from openrecognition.models.schemas import (
    GroupCreate,
    GroupEnrollmentOut,
    GroupEnrollmentsPut,
    GroupMemberOut,
    GroupMembersPut,
    GroupOut,
    GroupPatch,
)

router = APIRouter(prefix="/v1/auth/groups", tags=["auth"])


def _to_out(row: dict) -> GroupOut:
    return GroupOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        grants_role=row.get("grants_role"),
        sso_name=row.get("sso_name"),
        system=bool(row.get("system")),
        created_at=row["created_at"],
        member_count=int(row.get("member_count") or 0),
        enrollment_count=int(row.get("enrollment_count") or 0),
        members=[GroupMemberOut(**m) for m in row.get("members") or []],
        enrollments=[GroupEnrollmentOut(**e) for e in row.get("enrollments") or []],
    )


@router.get("", response_model=list[GroupOut])
def list_groups(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return [_to_out(row) for row in state.groups.list_groups()]


@router.post("", response_model=GroupOut)
def create_group(
    body: GroupCreate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        row = state.groups.create_group(body.name, body.description, body.sso_name)
    except ValueError as exc:
        raise bad_request("INVALID_GROUP", str(exc)) from exc
    return _to_out(row)


@router.get("/{group_id}", response_model=GroupOut)
def get_group(
    group_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    row = state.groups.get_group(group_id)
    if not row:
        raise not_found("Group not found")
    return _to_out(row)


@router.patch("/{group_id}", response_model=GroupOut)
def patch_group(
    group_id: str,
    body: GroupPatch,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise bad_request("EMPTY_PATCH", "Provide a name, description, or SSO name")
    try:
        row = state.groups.patch_group(
            group_id,
            name=data.get("name"),
            description=data.get("description"),
            sso_name=data.get("sso_name"),
            sso_name_set="sso_name" in data,
        )
    except ValueError as exc:
        raise bad_request("INVALID_GROUP", str(exc)) from exc
    if not row:
        raise not_found("Group not found")
    return _to_out(row)


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        if not state.groups.delete_group(group_id):
            raise not_found("Group not found")
    except ValueError as exc:
        raise bad_request("INVALID_GROUP", str(exc)) from exc


@router.put("/{group_id}/members", response_model=GroupOut)
def put_members(
    group_id: str,
    body: GroupMembersPut,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        row = state.groups.set_members(group_id, body.user_ids)
    except KeyError:
        raise not_found("Group not found")
    except ValueError as exc:
        raise bad_request("INVALID_GROUP", str(exc)) from exc
    return _to_out(row)


@router.put("/{group_id}/enrollments", response_model=GroupOut)
def put_enrollments(
    group_id: str,
    body: GroupEnrollmentsPut,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        row = state.groups.set_enrollments(
            group_id,
            [item.model_dump() for item in body.enrollments],
        )
    except KeyError:
        raise not_found("Group not found")
    except ValueError as exc:
        raise bad_request("INVALID_GROUP", str(exc)) from exc
    return _to_out(row)
