"""FastAPI dependencies."""

import uuid
from typing import Annotated

from fastapi import Depends, Header, Request

from openrecognition.api.errors import forbidden, maintenance, unauthorized
from openrecognition.app_state import AppState


def get_state(request: Request) -> AppState:
    return request.app.state.app_state


def get_request_id(
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> str:
    return x_request_id or str(uuid.uuid4())


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
        return {"scopes": ["admin", "read", "enroll", "recognize"], "name": "dev"}
    raw = _extract_key(authorization, x_api_key)
    if raw:
        auth = state.api_keys.authenticate(raw)
        if auth:
            return auth
        raise unauthorized()
    if request.url.path in ("/health", "/health/live", "/health/ready"):
        return None
    cookie = request.cookies.get("or_session")
    if cookie:
        sess = state.sessions.get_session(cookie)
        if sess:
            return {"scopes": sess["scopes"], "name": sess["username"], "user_id": sess["user_id"]}
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
