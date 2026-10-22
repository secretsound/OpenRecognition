"""FastAPI dependencies."""

import secrets
import uuid
from typing import Annotated

from fastapi import Depends, Header, Request

from openrecognition.api.errors import forbidden, maintenance, not_found, unauthorized
from openrecognition.app_state import AppState
from openrecognition.auth.sessions import role_from_scopes


def get_state(request: Request) -> AppState:
    return request.app.state.app_state


def get_request_id(
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> str:
    return x_request_id or str(uuid.uuid4())


def _metrics_token(presented: str, expected: str) -> bool:
    token = (expected or "").strip()
    if not presented or not token or len(presented) != len(token):
        return False
    return secrets.compare_digest(presented.encode(), token.encode())


def _extract_key(
    authorization: str | None,
    x_api_key: str | None,
) -> str | None:
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def get_auth(
    request: Request,
    state: Annotated[AppState, Depends(get_state)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> dict | None:
    exempt = (
        "/health",
        "/health/live",
        "/health/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api",
    )
    if state.maintenance_mode and not request.url.path.startswith("/v1/admin") and request.url.path not in exempt:
        raise maintenance()
    if not state.settings.auth_required:
        scopes = ["admin", "read", "enroll", "recognize"]
        return {"scopes": scopes, "name": "dev", "role": "admin"}
    raw = _extract_key(authorization, x_api_key)
    if raw and request.url.path == "/metrics" and _metrics_token(raw, state.settings.metrics_token):
        return {"scopes": ["read"], "name": "metrics", "role": "viewer"}
    if raw:
        auth = state.api_keys.authenticate(raw)
        if auth:
            return {**auth, "role": role_from_scopes(auth.get("scopes"))}
        raise unauthorized()
    if request.url.path in ("/health", "/health/live", "/health/ready"):
        return None
    cookie = request.cookies.get("or_session")
    if cookie:
        sess = state.sessions.get_session(cookie)
        if sess:
            return {
                "scopes": sess["scopes"],
                "name": sess["username"],
                "user_id": sess["user_id"],
                "role": sess["role"],
            }
    raise unauthorized()


def require_reader(request: Request, state: AppState) -> None:
    """Allow a signed-in reader or an API key with read access."""
    if not state.settings.auth_required:
        return
    raw = _extract_key(request.headers.get("authorization"), request.headers.get("x-api-key"))
    if raw:
        auth = state.api_keys.authenticate(raw)
        if not auth:
            raise unauthorized()
        scopes = auth.get("scopes") or []
        if "admin" in scopes or "read" in scopes:
            return
        raise forbidden("Scope 'read' required")
    cookie = request.cookies.get("or_session")
    if cookie:
        sess = state.sessions.get_session(cookie)
        if sess:
            scopes = sess.get("scopes") or []
            if sess.get("role") == "admin" or "admin" in scopes or "read" in scopes:
                return
            raise forbidden("Scope 'read' required")
    raise unauthorized()


def require_scope(scope: str):
    async def _checker(auth: Annotated[dict | None, Depends(get_auth)]) -> dict:
        if auth is None:
            raise unauthorized()
        if "admin" in auth.get("scopes", []):
            return auth
        if scope not in auth.get("scopes", []):
            raise forbidden(f"Scope '{scope}' required")
        return auth

    return _checker


_FULL_RIGHTS = {"view": True, "can_add_samples": True, "can_manage": True}
_VIEW_ONLY = {"view": True, "can_add_samples": False, "can_manage": False}
_NO_ACCESS = {"view": False, "can_add_samples": False, "can_manage": False}


def is_admin_access(auth: dict | None) -> bool:
    if not auth:
        return False
    if auth.get("role") == "admin":
        return True
    return "admin" in (auth.get("scopes") or [])


def is_service_account(auth: dict | None) -> bool:
    """API keys are not people. Enroll and admin keys keep the whole library."""
    if not auth or auth.get("user_id"):
        return False
    scopes = set(auth.get("scopes") or [])
    return bool(scopes & {"admin", "enroll"})


def is_unrestricted_library(auth: dict | None) -> bool:
    return is_admin_access(auth) or is_service_account(auth)


def library_limited_ids(state: AppState, auth: dict | None) -> set[str] | None:
    """Enrollment ids a caller may see, or None when they see the whole library."""
    if not auth or is_unrestricted_library(auth):
        return None
    user_id = auth.get("user_id")
    if not user_id:
        return None
    role = auth.get("role") or "viewer"
    granted = state.groups.limited_enrollment_ids(user_id)
    if role == "operator":
        return state.gallery.enrollment_ids_created_by(user_id) | granted
    if state.groups.is_library_limited(user_id, role):
        return granted
    return None


def enrollment_rights(state: AppState, auth: dict | None, enrollment_id: str) -> dict[str, bool]:
    if is_unrestricted_library(auth):
        return dict(_FULL_RIGHTS)
    user_id = auth.get("user_id") if auth else None
    if not user_id:
        return dict(_VIEW_ONLY)
    scopes = set((auth or {}).get("scopes") or [])
    if "enroll" in scopes and state.gallery.enrollment_owner(enrollment_id) == user_id:
        return dict(_FULL_RIGHTS)
    grant = state.groups.enrollment_rights(user_id, enrollment_id)
    if grant:
        return grant
    role = (auth or {}).get("role") or "viewer"
    if role == "operator" or state.groups.is_library_limited(user_id, role):
        return dict(_NO_ACCESS)
    return dict(_VIEW_ONLY)


def can_delete_enrollment(state: AppState, auth: dict | None, enrollment_id: str) -> bool:
    if is_unrestricted_library(auth):
        return True
    user_id = auth.get("user_id") if auth else None
    if not user_id:
        return False
    return state.gallery.enrollment_owner(enrollment_id) == user_id


def require_enrollment_view(state: AppState, auth: dict | None, enrollment_id: str) -> dict[str, bool]:
    rights = enrollment_rights(state, auth, enrollment_id)
    if not rights["view"]:
        raise not_found("Enrollment not found")
    return rights


def require_enrollment_right(
    state: AppState,
    auth: dict | None,
    enrollment_id: str,
    right: str,
) -> dict[str, bool]:
    rights = require_enrollment_view(state, auth, enrollment_id)
    if right == "add_samples" and rights["can_add_samples"]:
        return rights
    if right == "manage" and rights["can_manage"]:
        return rights
    raise forbidden("You do not have access to this enrollment")
