"""Single sign-on start, callback, and account linking."""

from __future__ import annotations

import html
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi.responses import HTMLResponse, RedirectResponse

from openrecognition.app_state import AppState
from openrecognition.auth.oidc import (
    OidcError,
    authorization_redirect,
    discover,
    exchange_code,
    group_claim,
    string_claim,
    verify_id_token,
)
from openrecognition.auth.saml import SamlError, authn_redirect, metadata_xml, verify_response
from openrecognition.config import Settings

logger = logging.getLogger("openrecognition.sso")

OIDC_CALLBACK_PATH = "/v1/auth/sso/oidc/callback"
SAML_ACS_PATH = "/v1/auth/sso/saml/acs"
SAML_METADATA_PATH = "/v1/auth/sso/saml/metadata"


class SsoError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def external_base(settings: Settings, request=None) -> str:
    configured = (settings.public_url or "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        return str(request.base_url).rstrip("/")
    return ""


def join_url(base: str, path: str) -> str:
    if not base:
        return ""
    return base.rstrip("/") + path


def safe_next(value: str | None) -> str:
    if not value:
        return "/"
    text = value.strip()
    if (
        len(text) > 500
        or not text.startswith("/")
        or text.startswith("//")
        or "\\" in text
        or "://" in text
        or "\n" in text
        or "\r" in text
    ):
        return "/"
    return text


def sp_entity_id(settings: Settings, request=None) -> str:
    explicit = (settings.saml_sp_entity_id or "").strip()
    if explicit:
        return explicit
    return join_url(external_base(settings, request), SAML_METADATA_PATH)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def put_state(state: AppState, payload: dict[str, Any]) -> str:
    state.db.execute(
        "DELETE FROM sso_login_states WHERE expires_at < ?",
        (_now().isoformat(),),
    )
    sid = secrets.token_urlsafe(24)
    expires = (_now() + timedelta(minutes=10)).isoformat()
    state.db.execute(
        "INSERT INTO sso_login_states (id, payload, expires_at) VALUES (?, ?, ?)",
        (sid, json.dumps(payload), expires),
    )
    return sid


def pop_state(state: AppState, sid: str) -> dict[str, Any] | None:
    if not sid or len(sid) > 200:
        return None
    with state.db.connect() as conn:
        row = conn.execute(
            "SELECT payload, expires_at FROM sso_login_states WHERE id = ?",
            (sid,),
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM sso_login_states WHERE id = ?", (sid,))
        conn.commit()
    expires = datetime.fromisoformat(row["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if _now() > expires:
        return None
    try:
        data = json.loads(row["payload"])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_username(raw: str) -> str:
    import re

    text = raw.strip()
    if len(text) > 64:
        text = text[:64]
    if not re.fullmatch(r"[A-Za-z0-9._@+-]{1,64}", text):
        raise SsoError("invalid")
    return text


def _sync_groups(state: AppState, user_id: str, groups: list[str]) -> None:
    try:
        state.groups.sync_sso_membership(user_id, groups)
    except ValueError:
        logger.warning("SSO group update skipped so the last admin stays an admin")


def login_identity(
    state: AppState,
    *,
    username: str,
    subject: str,
    protocol: str,
    groups: list[str],
    email: str | None = None,
) -> str:
    settings = state.settings
    try:
        user = state.sessions.provision_sso_user(
            username=_normalize_username(username),
            subject=subject[:256],
            protocol=protocol,
            role=settings.sso_default_role,
            link_existing=settings.sso_link_existing,
            auto_provision=settings.sso_auto_provision,
            email=email,
            match=settings.sso_match,
        )
    except ValueError as exc:
        text = str(exc)
        if "No account" in text:
            raise SsoError("unprovisioned") from exc
        raise SsoError("invalid") from exc
    _sync_groups(state, user["id"], groups)
    logger.info("SSO sign-in for %s", user["username"])
    return user["id"]


def start_login(state: AppState, request, next_path: str | None) -> str:
    settings = state.settings
    if not settings.sso_enabled:
        raise SsoError("failed")
    base = external_base(settings, request)
    if not base:
        raise SsoError("failed")
    nxt = safe_next(next_path)
    if settings.sso_protocol == "oidc":
        redirect_uri = join_url(base, OIDC_CALLBACK_PATH)
        nonce = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        sid = put_state(
            state,
            {"kind": "oidc", "next": nxt, "nonce": nonce, "verifier": verifier},
        )
        try:
            location = authorization_redirect(
                issuer=settings.oidc_issuer,
                client_id=settings.oidc_client_id,
                redirect_uri=redirect_uri,
                scope=settings.oidc_scopes or "openid profile email",
                state=sid,
                nonce=nonce,
                verifier=verifier,
            )
            assert_public_http(location)
            return location
        except (OidcError, ValueError) as exc:
            raise SsoError("failed") from exc
    if settings.sso_protocol == "saml":
        acs = join_url(base, SAML_ACS_PATH)
        entity = sp_entity_id(settings, request)
        request_id = "_" + secrets.token_urlsafe(18)
        sid = put_state(
            state,
            {"kind": "saml", "next": nxt, "request_id": request_id},
        )
        try:
            location = authn_redirect(
                sso_url=settings.saml_idp_sso_url,
                sp_entity_id=entity,
                acs_url=acs,
                request_id=request_id,
                relay_state=sid,
            )
            assert_public_http(location)
            return location
        except (SamlError, ValueError) as exc:
            raise SsoError("failed") from exc
    raise SsoError("failed")


def finish_oidc(state: AppState, request, code: str, sid: str) -> tuple[str, str]:
    settings = state.settings
    if not settings.sso_enabled or settings.sso_protocol != "oidc":
        raise SsoError("failed")
    payload = pop_state(state, sid)
    if not payload or payload.get("kind") != "oidc":
        raise SsoError("invalid")
    redirect_uri = join_url(external_base(settings, request), OIDC_CALLBACK_PATH)
    try:
        token = exchange_code(
            issuer=settings.oidc_issuer,
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            redirect_uri=redirect_uri,
            code=code,
            verifier=str(payload.get("verifier") or ""),
        )
        claims = verify_id_token(
            token,
            issuer=settings.oidc_issuer.rstrip("/"),
            client_id=settings.oidc_client_id,
            nonce=str(payload.get("nonce") or ""),
        )
        username = string_claim(claims, settings.sso_username_claim, "preferred_username", "email", "sub")
        groups = group_claim(claims, settings.oidc_groups_claim)
        subject = string_claim(claims, "sub")
        email = ""
        try:
            email = string_claim(claims, "email")
        except OidcError:
            email = username if "@" in username else ""
    except OidcError as exc:
        raise SsoError(exc.code) from exc
    user_id = login_identity(
        state,
        username=username,
        subject=subject,
        protocol="oidc",
        groups=groups,
        email=email or None,
    )
    return user_id, safe_next(str(payload.get("next") or "/"))


def finish_saml(state: AppState, request, saml_response: str, sid: str) -> tuple[str, str]:
    settings = state.settings
    if not settings.sso_enabled or settings.sso_protocol != "saml":
        raise SsoError("failed")
    payload = pop_state(state, sid)
    if not payload or payload.get("kind") != "saml":
        raise SsoError("invalid")
    import base64

    try:
        xml = base64.b64decode(saml_response, validate=False)
    except ValueError as exc:
        raise SsoError("invalid") from exc
    base = external_base(settings, request)
    try:
        identity = verify_response(
            xml,
            cert_pem=settings.saml_idp_x509_cert,
            idp_entity_id=settings.saml_idp_entity_id.strip(),
            sp_entity_id=sp_entity_id(settings, request),
            acs_url=join_url(base, SAML_ACS_PATH),
            request_id=str(payload.get("request_id") or ""),
            username_attr=settings.saml_username_attr.strip(),
            groups_attr=settings.saml_groups_attr.strip(),
        )
    except SamlError as exc:
        raise SsoError(exc.code) from exc
    user_id = login_identity(
        state,
        username=identity["username"],
        subject=f"saml:{identity['username']}",
        protocol="saml",
        groups=identity["groups"],
        email=identity.get("email") or None,
    )
    return user_id, safe_next(str(payload.get("next") or "/"))


def service_metadata(state: AppState, request) -> str:
    base = external_base(state.settings, request)
    return metadata_xml(
        entity_id=sp_entity_id(state.settings, request),
        acs_url=join_url(base, SAML_ACS_PATH),
    )


def signed_in_page(next_path: str) -> HTMLResponse:
    target = safe_next(next_path)
    script_target = json.dumps(target)
    page = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<meta http-equiv=\"refresh\" content=\"0;url={html.escape(target, quote=True)}\">"
        "<title>Signed in</title></head><body><p>Signed in. Continuing…</p>"
        f"<script>location.replace({script_target});</script></body></html>"
    )
    return HTMLResponse(
        page,
        headers={
            "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'",
            "Referrer-Policy": "no-referrer",
        },
    )


def login_error(code: str) -> RedirectResponse:
    allowed = {"denied", "failed", "unprovisioned", "invalid"}
    safe = code if code in allowed else "failed"
    return RedirectResponse(url=f"/login?sso_error={safe}", status_code=302)


def assert_public_http(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise SsoError("failed")


def check_oidc_issuer(issuer: str) -> dict[str, str]:
    document = discover(issuer)
    return {
        "issuer": str(document.get("issuer") or ""),
        "authorization_endpoint": str(document.get("authorization_endpoint") or ""),
        "token_endpoint": str(document.get("token_endpoint") or ""),
        "jwks_uri": str(document.get("jwks_uri") or ""),
    }
