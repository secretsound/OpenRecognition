"""API key and session auth routes."""

from fastapi import APIRouter, Depends, Request, Response

from openrecognition.api.deps import get_auth, get_state, require_scope
from openrecognition.api.errors import bad_request, not_found, rate_limited, unauthorized
from openrecognition.app_state import AppState
from openrecognition.auth.sessions import role_from_scopes
from openrecognition.integrator.mcp.scopes import (
    resolve_mcp_resources,
    resolve_mcp_tools,
    scopes_from_tool_names,
    validate_mcp_tool_names,
    validate_mcp_tools_fit_rest_scopes,
)
from openrecognition.models.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    AuthMeOut,
    LoginRequest,
    McpResourceOut,
    McpToolOut,
    SetupRequest,
    UserCreate,
    UserOut,
    UserPatch,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _cookie_secure(request: Request) -> bool:
    """Match the scheme the browser used. A Secure cookie is dropped on plain HTTP, including a LAN address."""
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if forwarded in {"https", "http"}:
        return forwarded == "https"
    return request.url.scheme == "https"


def _session_cookie(request: Request, response: Response, sid: str, max_age: int) -> None:
    response.set_cookie(
        key="or_session",
        value=sid,
        httponly=True,
        samesite="strict",
        secure=_cookie_secure(request),
        path="/",
        max_age=max_age,
    )


def _mcp_access(
    scopes: list[str],
    tool_allowlist: list[str] | None = None,
) -> tuple[list[McpToolOut], list[McpResourceOut]]:
    tools = resolve_mcp_tools(scopes, tool_allowlist)
    resources = resolve_mcp_resources(tools)
    return ([McpToolOut(**t) for t in tools], [McpResourceOut(**r) for r in resources])


def _resolve_key_create(body: ApiKeyCreate) -> tuple[list[str], list[str] | None]:
    rest_scopes = list(body.scopes or [])
    mcp_field_set = body.mcp_tools is not None

    if mcp_field_set:
        try:
            allowlist = validate_mcp_tool_names(body.mcp_tools or [])
        except ValueError as exc:
            raise bad_request("INVALID_MCP_TOOLS", str(exc)) from exc
        tool_scopes = scopes_from_tool_names(allowlist) if allowlist else []
        scopes = sorted(set(rest_scopes) | set(tool_scopes))
        if not scopes and not allowlist:
            raise bad_request(
                "INVALID_KEY",
                "Enable at least one REST scope and/or MCP tool",
            )
        if allowlist:
            try:
                validate_mcp_tools_fit_rest_scopes(allowlist, scopes)
            except ValueError as exc:
                raise bad_request("INVALID_MCP_TOOLS", str(exc)) from exc
        return scopes, allowlist

    if rest_scopes:
        return rest_scopes, None

    raise bad_request(
        "INVALID_KEY",
        "Enable REST API scopes and/or MCP tools (send mcp_tools: [] for API-only)",
    )


@router.get("/me", response_model=AuthMeOut)
def auth_me(auth=Depends(get_auth)):
    if not auth:
        raise unauthorized()
    scopes = auth.get("scopes") or []
    allowlist = auth.get("mcp_tool_allowlist")
    tools, resources = _mcp_access(scopes, allowlist)
    credential_type = "session" if auth.get("user_id") else "api_key"
    return AuthMeOut(
        credential_type=credential_type,
        name=auth.get("name") or "unknown",
        scopes=scopes,
        role=auth.get("role") or role_from_scopes(scopes),
        mcp_tools=tools,
        mcp_resources=resources,
    )


@router.post("/keys", response_model=ApiKeyCreated)
def create_key(
    body: ApiKeyCreate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    scopes, allowlist = _resolve_key_create(body)
    created = state.api_keys.create_key(
        body.name, scopes, mcp_tools=allowlist
    )
    payload = {
        k: v
        for k, v in created.items()
        if k not in ("revoked_at", "key", "mcp_tool_allowlist")
    }
    payload["mcp_tool_allowlist"] = created.get("mcp_tool_allowlist")
    mcp_tools, mcp_resources = _mcp_access(scopes, allowlist)
    return ApiKeyCreated(
        **payload,
        key=created["key"],
        mcp_tools=mcp_tools,
        mcp_resources=mcp_resources,
    )


@router.get("/keys", response_model=list[ApiKeyOut])
def list_keys(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return [
        ApiKeyOut(**k)
        for k in state.api_keys.list_keys()
        if k.get("revoked_at") is None
    ]


@router.delete("/keys/{key_id}", status_code=204)
def revoke_key(
    key_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    if not state.api_keys.revoke_key(key_id):
        from openrecognition.api.errors import not_found

        raise not_found("API key not found")


@router.get("/users", response_model=list[UserOut])
def list_users(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    return [UserOut(**u) for u in state.sessions.list_users()]


@router.post("/users", response_model=UserOut)
def create_user(
    body: UserCreate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        user = state.sessions.create_user(body.username, body.password, body.role)
    except ValueError as e:
        code = "USERNAME_TAKEN" if "already exists" in str(e).lower() else "INVALID_USER"
        raise bad_request(code, str(e))
    return UserOut(**user)


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: str,
    body: UserPatch,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
    _admin=Depends(require_scope("admin")),
):
    if not body.role and not body.password:
        raise bad_request("EMPTY_PATCH", "Provide role and/or password to update")
    try:
        user = state.sessions.update_user(
            user_id,
            role=body.role,
            password=body.password,
        )
    except ValueError as e:
        raise bad_request("INVALID_USER", str(e))
    if not user:
        raise not_found("User not found")
    return UserOut(**user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
    _admin=Depends(require_scope("admin")),
):
    actor_id = auth.get("user_id") if auth else None
    try:
        if not state.sessions.delete_user(user_id, actor_user_id=actor_id):
            raise not_found("User not found")
    except ValueError as e:
        raise bad_request("INVALID_USER", str(e))


@router.get("/setup")
def setup_status(state: AppState = Depends(get_state)):
    return {"required": not state.sessions.has_users()}


@router.post("/setup")
def setup_admin(
    body: SetupRequest,
    request: Request,
    response: Response,
    state: AppState = Depends(get_state),
):
    if state.sessions.has_users():
        raise bad_request("ALREADY_CONFIGURED", "An admin account already exists")
    username = body.username.strip()
    try:
        user = state.sessions.create_user(username, body.password, "admin")
    except ValueError as exc:
        raise bad_request("INVALID_ACCOUNT", str(exc)) from exc
    sid = state.sessions.create_session(user["id"])
    _session_cookie(request, response, sid, state.settings.session_ttl_minutes * 60)
    return {"username": user["username"], "role": user["role"]}


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    state: AppState = Depends(get_state),
):
    client_host = request.client.host if request.client else "unknown"
    if not state.login_limiter.allow(client_host, state.settings.auth_rate_limit_per_minute):
        raise rate_limited()
    user = state.sessions.authenticate_user(body.username, body.password)
    if not user:
        raise unauthorized("Invalid credentials")
    sid = state.sessions.create_session(user["id"])
    _session_cookie(request, response, sid, state.settings.session_ttl_minutes * 60)
    return {"session_id": sid, "username": user["username"], "role": user["role"]}


@router.post("/logout")
def logout(request: Request, response: Response, state: AppState = Depends(get_state)):
    sid = request.cookies.get("or_session")
    if sid:
        state.sessions.delete_session(sid)
    response.delete_cookie(
        "or_session",
        path="/",
        httponly=True,
        samesite="strict",
        secure=_cookie_secure(request),
    )
    return {"ok": True}
