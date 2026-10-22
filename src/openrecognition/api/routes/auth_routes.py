"""API key and session auth routes."""

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.responses import Response as RawResponse

from openrecognition.api.deps import get_auth, get_state, library_limited_ids, require_scope
from openrecognition.api.errors import bad_request, not_found, rate_limited, unauthorized
from openrecognition.app_state import AppState
from openrecognition.auth.sessions import role_from_scopes
from openrecognition.auth.sso import (
    SsoError,
    finish_oidc,
    finish_saml,
    login_error,
    service_metadata,
    signed_in_page,
    start_login,
)
from openrecognition.integrator.mcp.scopes import (
    normalize_key_scopes,
    resolve_mcp_resources,
    resolve_mcp_tools,
    scopes_from_tool_names,
    validate_mcp_tool_names,
)
from openrecognition.models.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    ApiKeyUpdate,
    AuthMeOut,
    EnrollmentGrantOut,
    GroupBriefOut,
    LoginRequest,
    McpResourceOut,
    McpToolOut,
    SetupRequest,
    UiConfigOut,
    UserCreate,
    UserOut,
    UserPatch,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _cookie_secure(request: Request) -> bool:
    """Match the scheme the browser used. Forwarded scheme is applied only for a trusted proxy."""
    return request.url.scheme == "https"


def _session_cookie(
    request: Request,
    response: Response,
    sid: str,
    max_age: int,
    *,
    samesite: str = "strict",
) -> None:
    response.set_cookie(
        key="or_session",
        value=sid,
        httponly=True,
        samesite=samesite,
        secure=_cookie_secure(request),
        path="/",
        max_age=max_age,
    )


def _mcp_access(scopes: list[str]) -> tuple[list[McpToolOut], list[McpResourceOut]]:
    tools = resolve_mcp_tools(scopes, None)
    resources = resolve_mcp_resources(tools)
    return ([McpToolOut(**t) for t in tools], [McpResourceOut(**r) for r in resources])


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise bad_request("INVALID_KEY", "Name is required")
    if len(cleaned) > 80:
        raise bad_request("INVALID_KEY", "Use 80 characters or fewer")
    return cleaned


def _scopes_from_body(
    scopes: list[str] | None,
    mcp_tools: list[str] | None = None,
) -> list[str]:
    """Permissions cover the REST API and MCP. Tool names only fill in a missing list."""
    chosen = list(scopes or [])
    if not chosen and mcp_tools:
        try:
            names = validate_mcp_tool_names(mcp_tools)
        except ValueError as exc:
            raise bad_request("INVALID_KEY", str(exc)) from exc
        chosen = scopes_from_tool_names(names)
    try:
        return normalize_key_scopes(chosen)
    except ValueError as exc:
        raise bad_request("INVALID_KEY", str(exc)) from exc


def _user_out(state: AppState, user: dict) -> UserOut:
    return UserOut(
        **{k: user[k] for k in ("id", "username", "role", "created_at")},
        email=user.get("email"),
        groups=[GroupBriefOut(**g) for g in state.groups.briefs_for_user(user["id"])],
    )


@router.get("/me", response_model=AuthMeOut)
def auth_me(
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
):
    if not auth:
        raise unauthorized()
    scopes = auth.get("scopes") or []
    tools, resources = _mcp_access(scopes)
    credential_type = "session" if auth.get("user_id") else "api_key"
    user_id = auth.get("user_id")
    role = auth.get("role") or role_from_scopes(scopes)
    groups = state.groups.briefs_for_user(user_id) if user_id else []
    grants = state.groups.enrollment_grants_for_user(user_id) if user_id else []
    limited = library_limited_ids(state, auth) is not None
    return AuthMeOut(
        credential_type=credential_type,
        name=auth.get("name") or "unknown",
        scopes=scopes,
        role=role,
        mcp_tools=tools,
        mcp_resources=resources,
        groups=[GroupBriefOut(**g) for g in groups],
        enrollment_grants=[EnrollmentGrantOut(**g) for g in grants],
        library_limited=limited,
    )


@router.post("/keys", response_model=ApiKeyCreated)
def create_key(
    body: ApiKeyCreate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    scopes = _scopes_from_body(body.scopes, body.mcp_tools)
    created = state.api_keys.create_key(_clean_name(body.name), scopes)
    payload = {
        k: v
        for k, v in created.items()
        if k not in ("revoked_at", "key")
    }
    mcp_tools, mcp_resources = _mcp_access(scopes)
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


@router.patch("/keys/{key_id}", response_model=ApiKeyOut)
def update_key(
    key_id: str,
    body: ApiKeyUpdate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    if body.name is None and body.scopes is None:
        raise bad_request("EMPTY_PATCH", "Provide a name or permissions to update")
    name = _clean_name(body.name) if body.name is not None else None
    scopes = _scopes_from_body(body.scopes) if body.scopes is not None else None
    updated = state.api_keys.update_key(key_id, name=name, scopes=scopes)
    if not updated:
        raise not_found("API key not found")
    return ApiKeyOut(**updated)


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
    return [_user_out(state, u) for u in state.sessions.list_users()]


@router.post("/users", response_model=UserOut)
def create_user(
    body: UserCreate,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("admin")),
):
    try:
        user = state.sessions.create_user(
            body.username, body.password, body.role, email=body.email
        )
        if body.group_ids is not None:
            state.groups.set_user_groups(user["id"], body.group_ids)
    except ValueError as e:
        code = "USERNAME_TAKEN" if "already exists" in str(e).lower() else "INVALID_USER"
        raise bad_request(code, str(e))
    return _user_out(state, user)


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: str,
    body: UserPatch,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
    _admin=Depends(require_scope("admin")),
):
    email_set = "email" in body.model_fields_set
    if not body.role and not body.password and body.group_ids is None and not email_set:
        raise bad_request("EMPTY_PATCH", "Provide role, password, email, and/or groups to update")
    try:
        user = state.sessions.update_user(
            user_id,
            role=body.role,
            password=body.password,
            email=body.email,
            email_set=email_set,
        )
        if user and body.group_ids is not None:
            state.groups.set_user_groups(user_id, body.group_ids)
            user = state.sessions.get_user(user_id)
    except KeyError:
        raise not_found("User not found")
    except ValueError as e:
        raise bad_request("INVALID_USER", str(e))
    if not user:
        raise not_found("User not found")
    return _user_out(state, user)


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
        user = state.sessions.create_user(username, body.password, "admin", email=body.email)
    except ValueError as exc:
        raise bad_request("INVALID_ACCOUNT", str(exc)) from exc
    sid = state.sessions.create_session(user["id"])
    _session_cookie(request, response, sid, state.settings.session_ttl_minutes * 60)
    role = state.groups.effective_role(user["id"], user["role"])
    return {"username": user["username"], "role": role}


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
    role = state.groups.effective_role(user["id"], user["role"])
    return {"session_id": sid, "username": user["username"], "role": role}


@router.post("/logout")
def logout(request: Request, response: Response, state: AppState = Depends(get_state)):
    sid = request.cookies.get("or_session")
    if sid:
        state.sessions.delete_session(sid)
    for samesite in ("strict", "lax"):
        response.delete_cookie(
            "or_session",
            path="/",
            httponly=True,
            samesite=samesite,
            secure=_cookie_secure(request),
        )
    return {"ok": True}


@router.get("/ui", response_model=UiConfigOut)
def ui_config(state: AppState = Depends(get_state)):
    settings = state.settings
    return UiConfigOut(
        display_language=settings.display_language,
        display_timezone=settings.display_timezone or "UTC",
        sso_enabled=settings.sso_enabled,
        sso_protocol=settings.sso_protocol,
        sso_label=settings.sso_label or "Single sign-on",
    )


@router.get("/sso/start")
def sso_start(request: Request, state: AppState = Depends(get_state), next: str | None = None):
    try:
        location = start_login(state, request, next)
    except SsoError as exc:
        return login_error(exc.code)
    return RedirectResponse(url=location, status_code=302)


@router.get("/sso/oidc/callback")
def sso_oidc_callback(
    request: Request,
    response: Response,
    app_state: AppState = Depends(get_state),
    code: str = "",
    error: str = "",
):
    # The IdP sends `state` as a query parameter. Keep that name off this signature.
    sid = request.query_params.get("state") or ""
    if error:
        return login_error("denied" if error == "access_denied" else "failed")
    if not code or not sid:
        return login_error("invalid")
    client_host = request.client.host if request.client else "unknown"
    if not app_state.login_limiter.allow(client_host, app_state.settings.auth_rate_limit_per_minute):
        return login_error("failed")
    try:
        user_id, nxt = finish_oidc(app_state, request, code, sid)
    except SsoError as exc:
        return login_error(exc.code)
    page = signed_in_page(nxt)
    sid_cookie = app_state.sessions.create_session(user_id)
    _session_cookie(request, page, sid_cookie, app_state.settings.session_ttl_minutes * 60, samesite="lax")
    return page


@router.post("/sso/saml/acs")
def sso_saml_acs(
    request: Request,
    response: Response,
    state: AppState = Depends(get_state),
    SAMLResponse: str = Form(""),
    RelayState: str = Form(""),
):
    if not SAMLResponse:
        return login_error("invalid")
    client_host = request.client.host if request.client else "unknown"
    if not state.login_limiter.allow(client_host, state.settings.auth_rate_limit_per_minute):
        return login_error("failed")
    try:
        user_id, nxt = finish_saml(state, request, SAMLResponse, RelayState)
    except SsoError as exc:
        return login_error(exc.code)
    page = signed_in_page(nxt)
    sid_cookie = state.sessions.create_session(user_id)
    _session_cookie(request, page, sid_cookie, state.settings.session_ttl_minutes * 60, samesite="lax")
    return page


@router.get("/sso/saml/metadata")
def sso_saml_metadata(request: Request, state: AppState = Depends(get_state)):
    xml = service_metadata(state, request)
    return RawResponse(content=xml, media_type="application/samlmetadata+xml")
