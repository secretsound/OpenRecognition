"""Validate and apply settings edited from the console."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from openrecognition.api.errors import bad_request
from openrecognition.app_state import AppState
from openrecognition.auth.oidc import require_http_url
from openrecognition.auth.saml import normalize_cert_pem
from openrecognition.auth.sso import (
    OIDC_CALLBACK_PATH,
    SAML_ACS_PATH,
    SAML_METADATA_PATH,
    external_base,
    join_url,
    sp_entity_id,
)
from openrecognition.boot_settings import (
    ENV_ONLY_KEYS,
    LANGUAGES,
    LOG_LEVELS,
    RESTART_KEYS,
    SSO_PROTOCOLS,
    SSO_ROLES,
    restart_pending,
    valid_metrics_token,
    valid_timezone,
)
from openrecognition.logging_config import log_file_path
from openrecognition.models.schemas import (
    AppSettingsOut,
    AppSettingsPatch,
    HardwareOut,
    ServerLogsOut,
    SystemInfoOut,
)
from openrecognition.system_info import collect_system_info
from openrecognition.tls_material import inspect_files, write_pair

_BLOCKED = (Path("/proc"), Path("/sys"), Path("/dev"), Path("/boot"))
_CLAIM = re.compile(r"^[A-Za-z0-9_.:/-]{1,80}$")


def _fail(message: str) -> None:
    raise bad_request("INVALID_SETTINGS", message)


def _limit(proposed: dict, key: str, low: int, high: int, label: str) -> None:
    try:
        value = int(proposed[key])
    except (TypeError, ValueError):
        _fail(f"{label} must be a number")
    if not low <= value <= high:
        _fail(f"{label} must be between {low} and {high}")
    proposed[key] = value


def _directory(value: str, *, label: str, data_dir: Path) -> Path:
    text = value.strip()
    if not text or "\x00" in text or any(char in text for char in "\r\n") or len(text) > 500:
        _fail(f"{label} is empty or invalid")
    try:
        resolved = Path(text).expanduser().resolve()
    except OSError:
        _fail(f"{label} is invalid")
    if resolved == Path("/"):
        _fail(f"{label} cannot be the filesystem root")
    for blocked in _BLOCKED:
        if resolved == blocked or blocked in resolved.parents:
            _fail(f"{label} cannot be inside {blocked}")
    if resolved.exists() and not resolved.is_dir():
        _fail(f"{label} is a file")
    try:
        data_resolved = Path(data_dir).expanduser().resolve()
    except OSError:
        data_resolved = Path(data_dir)
    if resolved == data_resolved:
        _fail(f"{label} cannot be the data directory")
    return resolved


def _trusted_proxies(value: str, *, required: bool) -> str:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if required and not parts:
        _fail("Add at least one trusted proxy, or turn reverse proxy support off")
    cleaned: list[str] = []
    for part in parts:
        if part == "*":
            cleaned.append("*")
            continue
        try:
            if "/" in part:
                cleaned.append(str(ipaddress.ip_network(part, strict=False)))
            else:
                cleaned.append(str(ipaddress.ip_address(part)))
        except ValueError:
            _fail(f"Trusted proxy “{part}” is not an IP address or CIDR range")
    return ", ".join(cleaned)


def _claim(value: str, label: str, *, allow_empty: bool = False) -> str:
    text = value.strip()
    if not text and allow_empty:
        return ""
    if not _CLAIM.fullmatch(text):
        _fail(f"{label} contains unsupported characters")
    return text


def _merged(state: AppState, body: AppSettingsPatch):
    settings = state.settings
    def pick(name: str, current):
        value = getattr(body, name)
        return current if value is None else value

    return {
        "public_url": pick("public_url", settings.public_url),
        "behind_proxy": pick("behind_proxy", settings.behind_proxy),
        "trusted_proxies": pick("trusted_proxies", settings.trusted_proxies),
        "display_language": pick("display_language", settings.display_language),
        "display_timezone": pick("display_timezone", settings.display_timezone),
        "auth_rate_limit_per_minute": pick("auth_rate_limit_per_minute", settings.auth_rate_limit_per_minute),
        "video_max_upload_bytes": pick("video_max_upload_bytes", settings.video_max_upload_bytes),
        "log_max_mb": pick("log_max_mb", settings.log_max_mb),
        "log_backup_count": pick("log_backup_count", settings.log_backup_count),
        "health_detail_public": pick("health_detail_public", settings.health_detail_public),
        "host": pick("host", settings.host),
        "port": pick("port", settings.port),
        "http_enabled": pick("http_enabled", settings.http_enabled),
        "https_enabled": pick("https_enabled", settings.https_enabled),
        "https_port": pick("https_port", settings.https_port),
        "tls_cert_file": pick("tls_cert_file", settings.tls_cert_file),
        "tls_key_file": pick("tls_key_file", settings.tls_key_file),
        "models_dir": pick("models_dir", str(settings.models_dir)),
        "model_packs_dir": pick("model_packs_dir", str(settings.model_packs_dir)),
        "logs_dir": pick("logs_dir", settings.logs_dir),
        "log_level": pick("log_level", settings.log_level),
        "log_to_file": pick("log_to_file", settings.log_to_file),
        "sso_enabled": pick("sso_enabled", settings.sso_enabled),
        "sso_protocol": pick("sso_protocol", settings.sso_protocol),
        "sso_label": pick("sso_label", settings.sso_label),
        "sso_auto_provision": pick("sso_auto_provision", settings.sso_auto_provision),
        "sso_default_role": pick("sso_default_role", settings.sso_default_role),
        "sso_link_existing": pick("sso_link_existing", settings.sso_link_existing),
        "sso_match": pick("sso_match", settings.sso_match),
        "sso_username_claim": pick("sso_username_claim", settings.sso_username_claim),
        "oidc_issuer": pick("oidc_issuer", settings.oidc_issuer),
        "oidc_client_id": pick("oidc_client_id", settings.oidc_client_id),
        "oidc_scopes": pick("oidc_scopes", settings.oidc_scopes),
        "oidc_groups_claim": pick("oidc_groups_claim", settings.oidc_groups_claim),
        "saml_idp_entity_id": pick("saml_idp_entity_id", settings.saml_idp_entity_id),
        "saml_idp_sso_url": pick("saml_idp_sso_url", settings.saml_idp_sso_url),
        "saml_idp_x509_cert": pick("saml_idp_x509_cert", settings.saml_idp_x509_cert),
        "saml_sp_entity_id": pick("saml_sp_entity_id", settings.saml_sp_entity_id),
        "saml_username_attr": pick("saml_username_attr", settings.saml_username_attr),
        "saml_groups_attr": pick("saml_groups_attr", settings.saml_groups_attr),
    }


def _validate_site(state: AppState, body: AppSettingsPatch) -> dict:
    proposed = _merged(state, body)
    try:
        public = require_http_url(str(proposed["public_url"]), name="Application URL") if str(proposed["public_url"]).strip() else ""
    except ValueError as exc:
        _fail(str(exc))
    proposed["public_url"] = public
    language = str(proposed["display_language"]).strip().lower().replace("_", "-")
    aliases = {"zh-cn": "zh", "zh-hans": "zh", "pt-br": "pt", "en-us": "en", "en-gb": "en"}
    language = aliases.get(language, language.split("-")[0])
    if language not in LANGUAGES:
        _fail("Choose a supported display language")
    proposed["display_language"] = language
    zone = str(proposed["display_timezone"]).strip() or "UTC"
    if not valid_timezone(zone):
        _fail("Choose a time zone from the IANA list, such as America/Los_Angeles")
    proposed["display_timezone"] = zone
    _limit(proposed, "auth_rate_limit_per_minute", 1, 10_000, "Sign-in rate limit")
    _limit(proposed, "video_max_upload_bytes", 1024 * 1024, 2 * 1024 * 1024 * 1024, "Upload limit")
    _limit(proposed, "log_max_mb", 1, 200, "Log file size")
    _limit(proposed, "log_backup_count", 1, 30, "Log files to keep")
    host = str(proposed["host"]).strip()
    if not host or len(host) > 255 or any(char in host for char in " \t\r\n/\\"):
        _fail("Bind address is invalid")
    proposed["host"] = host
    http_port = int(proposed["port"])
    https_port = int(proposed["https_port"])
    if not (1 <= http_port <= 65535 and 1 <= https_port <= 65535):
        _fail("Ports must be between 1 and 65535")
    if proposed["http_enabled"] and proposed["https_enabled"] and http_port == https_port:
        _fail("HTTP and HTTPS need different ports")
    if not proposed["http_enabled"] and not proposed["https_enabled"]:
        _fail("Leave HTTP or HTTPS enabled")
    proposed["trusted_proxies"] = _trusted_proxies(
        str(proposed["trusted_proxies"]),
        required=bool(proposed["behind_proxy"]),
    )
    level = str(proposed["log_level"]).strip().lower()
    if level not in LOG_LEVELS:
        _fail("Log level must be debug, info, warning, or error")
    proposed["log_level"] = level
    if str(proposed["logs_dir"]).strip():
        proposed["logs_dir"] = str(
            _directory(str(proposed["logs_dir"]), label="Log directory", data_dir=state.settings.data_dir)
        )
    else:
        proposed["logs_dir"] = ""
    proposed["models_dir"] = str(
        _directory(str(proposed["models_dir"]), label="Models directory", data_dir=state.settings.data_dir)
    )
    proposed["model_packs_dir"] = str(
        _directory(str(proposed["model_packs_dir"]), label="Model packs directory", data_dir=state.settings.data_dir)
    )
    token = state.settings.metrics_token
    if body.clear_metrics_token:
        token = ""
    if body.metrics_token:
        token = body.metrics_token.strip()
    if token and not valid_metrics_token(token):
        _fail("Metrics token must be 16–128 letters, numbers, underscores, or hyphens")
    proposed["metrics_token"] = token
    secret = state.settings.oidc_client_secret
    if body.clear_oidc_client_secret:
        secret = ""
    if body.oidc_client_secret:
        secret = body.oidc_client_secret.strip()
    proposed["oidc_client_secret"] = secret
    protocol = str(proposed["sso_protocol"]).strip().lower()
    if protocol not in SSO_PROTOCOLS:
        _fail("Single sign-on protocol must be OIDC or SAML")
    proposed["sso_protocol"] = protocol
    role = str(proposed["sso_default_role"]).strip()
    if role not in SSO_ROLES:
        _fail("Default role must be viewer, operator, or admin")
    proposed["sso_default_role"] = role
    match = str(proposed["sso_match"]).strip().lower()
    if match not in ("username", "email"):
        _fail("Match existing accounts by username or email")
    proposed["sso_match"] = match
    label = " ".join(str(proposed["sso_label"]).split())
    if not label:
        label = "Single sign-on"
    if len(label) > 40:
        _fail("Single sign-on button label is too long")
    proposed["sso_label"] = label
    proposed["sso_username_claim"] = _claim(str(proposed["sso_username_claim"]), "Username claim")
    proposed["oidc_groups_claim"] = _claim(str(proposed["oidc_groups_claim"]), "Groups claim", allow_empty=True)
    proposed["saml_username_attr"] = _claim(str(proposed["saml_username_attr"]) or "uid", "Username attribute")
    proposed["saml_groups_attr"] = _claim(str(proposed["saml_groups_attr"]), "Groups attribute", allow_empty=True)
    if str(proposed["oidc_issuer"]).strip():
        try:
            proposed["oidc_issuer"] = require_http_url(str(proposed["oidc_issuer"]), name="Issuer URL")
        except ValueError as exc:
            _fail(str(exc))
    else:
        proposed["oidc_issuer"] = ""
    scopes = " ".join(str(proposed["oidc_scopes"]).split())
    if scopes and "openid" not in scopes.split():
        _fail("OIDC scopes must include openid")
    proposed["oidc_scopes"] = scopes or "openid profile email"
    if str(proposed["saml_idp_sso_url"]).strip():
        try:
            proposed["saml_idp_sso_url"] = require_http_url(str(proposed["saml_idp_sso_url"]), name="IdP sign-in URL")
        except ValueError as exc:
            _fail(str(exc))
    else:
        proposed["saml_idp_sso_url"] = ""
    if str(proposed["saml_idp_x509_cert"]).strip():
        try:
            proposed["saml_idp_x509_cert"] = normalize_cert_pem(str(proposed["saml_idp_x509_cert"]))
        except ValueError as exc:
            _fail(str(exc))
    else:
        proposed["saml_idp_x509_cert"] = ""
    proposed["saml_idp_entity_id"] = str(proposed["saml_idp_entity_id"]).strip()
    proposed["saml_sp_entity_id"] = str(proposed["saml_sp_entity_id"]).strip()
    proposed["oidc_client_id"] = str(proposed["oidc_client_id"]).strip()
    if proposed["sso_enabled"] and protocol == "oidc":
        if not proposed["oidc_issuer"] or not proposed["oidc_client_id"] or not secret:
            _fail("OIDC needs an issuer, client ID, and client secret")
    if proposed["sso_enabled"] and protocol == "saml":
        if not proposed["saml_idp_entity_id"] or not proposed["saml_idp_sso_url"] or not proposed["saml_idp_x509_cert"]:
            _fail("SAML needs an entity ID, sign-in URL, and signing certificate")
    pem_cert = (body.tls_cert_pem or "").strip()
    pem_key = (body.tls_key_pem or "").strip()
    if bool(pem_cert) != bool(pem_key):
        _fail("Paste both the certificate and the private key")
    if pem_cert and pem_key:
        try:
            cert_file, key_file = write_pair(state.settings, pem_cert, pem_key)
        except ValueError as exc:
            _fail(str(exc))
        proposed["tls_cert_file"] = cert_file
        proposed["tls_key_file"] = key_file
    if proposed["https_enabled"]:
        status = inspect_files(str(proposed["tls_cert_file"]), str(proposed["tls_key_file"]))
        if not status["tls_readable"]:
            _fail(status["tls_error"] or "Add a certificate and private key before turning HTTPS on")
    return proposed


def apply_settings_patch(state: AppState, body: AppSettingsPatch) -> None:
    site = _validate_site(state, body)
    if body.inference_backend is not None:
        state.settings.inference_backend = body.inference_backend
        state.inference_policy.set_backend(body.inference_backend)
    if body.maintenance_mode is not None:
        state.maintenance_mode = body.maintenance_mode
    if body.enrollment_media_retention is not None:
        if body.enrollment_media_retention not in ("keep", "embeddings_only"):
            raise bad_request(
                "INVALID_RETENTION",
                "enrollment_media_retention must be 'keep' or 'embeddings_only'",
            )
        state.settings.enrollment_media_retention = body.enrollment_media_retention  # type: ignore[assignment]
    if body.feature_flags is not None:
        state.feature_flags.update(body.feature_flags)
    if body.default_min_confidence is not None:
        state.default_min_confidence = body.default_min_confidence
    if body.default_return_unknown is not None:
        state.default_return_unknown = body.default_return_unknown
    if body.default_include_sound_events is not None:
        state.default_include_sound_events = body.default_include_sound_events
    if body.recognition_log_retention_days is not None:
        state.recognition_logs.set_retention_days(body.recognition_log_retention_days)
        state.recognition_logs.prune_old()
    if body.session_ttl_minutes is not None:
        state.settings.session_ttl_minutes = body.session_ttl_minutes
        state.sessions.ttl_minutes = body.session_ttl_minutes
    if body.model_idle_unload_minutes is not None:
        state.settings.model_idle_unload_minutes = body.model_idle_unload_minutes
        state.pool.idle_unload_minutes = body.model_idle_unload_minutes
    if "onnx_intra_op_threads" in body.model_fields_set:
        state.thread_override = body.onnx_intra_op_threads
        state.apply_threads()
    settings = state.settings
    for key, value in site.items():
        if key in {"models_dir", "model_packs_dir"}:
            setattr(settings, key, Path(value))
        else:
            setattr(settings, key, value)


def settings_response(state: AppState) -> AppSettingsOut:
    settings = state.settings
    store = state._runtime_store
    base = external_base(settings)
    tls = inspect_files(settings.tls_cert_file, settings.tls_key_file)
    return AppSettingsOut(
        maintenance_mode=state.maintenance_mode,
        enrollment_media_retention=settings.enrollment_media_retention,
        inference_backend=state.inference_policy.backend,
        inference_status=state.inference_policy.status(),
        feature_flags=dict(state.feature_flags),
        default_min_confidence=state.default_min_confidence,
        default_return_unknown=state.default_return_unknown,
        default_include_sound_events=state.default_include_sound_events,
        recognition_log_retention_days=state.recognition_logs.retention_days,
        hardware=HardwareOut(**state.hardware_info()),
        auth_required=settings.auth_required,
        docs_enabled=settings.docs_enabled,
        web_enabled=settings.web_enabled,
        data_dir=str(settings.data_dir),
        models_dir=str(settings.models_dir),
        model_packs_dir=str(settings.model_packs_dir),
        session_ttl_minutes=settings.session_ttl_minutes,
        mqtt_enabled=settings.mqtt_enabled,
        mqtt_host=settings.mqtt_host,
        mqtt_port=settings.mqtt_port,
        mqtt_topic_prefix=settings.mqtt_topic_prefix,
        model_idle_unload_minutes=settings.model_idle_unload_minutes,
        auth_rate_limit_per_minute=settings.auth_rate_limit_per_minute,
        host=settings.host,
        port=settings.port,
        http_enabled=settings.http_enabled,
        https_enabled=settings.https_enabled,
        https_port=settings.https_port,
        tls_cert_file=settings.tls_cert_file,
        tls_key_file=settings.tls_key_file,
        tls_configured=bool(tls["tls_configured"]),
        tls_readable=bool(tls["tls_readable"]),
        tls_subject=str(tls["tls_subject"]),
        tls_expires_at=str(tls["tls_expires_at"]),
        tls_error=str(tls["tls_error"]),
        public_url=settings.public_url,
        behind_proxy=settings.behind_proxy,
        trusted_proxies=settings.trusted_proxies,
        display_language=settings.display_language,
        display_timezone=settings.display_timezone or "UTC",
        logs_dir=settings.logs_dir,
        log_level=settings.log_level,
        log_to_file=settings.log_to_file,
        log_max_mb=settings.log_max_mb,
        log_backup_count=settings.log_backup_count,
        log_file=str(log_file_path(settings)),
        video_max_upload_bytes=settings.video_max_upload_bytes,
        health_detail_public=settings.health_detail_public,
        metrics_token_set=bool(settings.metrics_token),
        sso_enabled=settings.sso_enabled,
        sso_protocol=settings.sso_protocol,
        sso_label=settings.sso_label,
        sso_auto_provision=settings.sso_auto_provision,
        sso_default_role=settings.sso_default_role,
        sso_link_existing=settings.sso_link_existing,
        sso_match=settings.sso_match,
        sso_username_claim=settings.sso_username_claim,
        oidc_issuer=settings.oidc_issuer,
        oidc_client_id=settings.oidc_client_id,
        oidc_client_secret_set=bool(settings.oidc_client_secret),
        oidc_scopes=settings.oidc_scopes,
        oidc_groups_claim=settings.oidc_groups_claim,
        saml_idp_entity_id=settings.saml_idp_entity_id,
        saml_idp_sso_url=settings.saml_idp_sso_url,
        saml_idp_x509_cert=settings.saml_idp_x509_cert,
        saml_sp_entity_id=settings.saml_sp_entity_id,
        saml_username_attr=settings.saml_username_attr,
        saml_groups_attr=settings.saml_groups_attr,
        sso_redirect_uri=join_url(base, OIDC_CALLBACK_PATH),
        sso_acs_url=join_url(base, SAML_ACS_PATH),
        sso_metadata_url=join_url(base, SAML_METADATA_PATH),
        sso_sp_entity_id=sp_entity_id(settings) if base or settings.saml_sp_entity_id else "",
        runtime_settings_path=str(store.path) if store else "",
        restart_required_for=list(RESTART_KEYS),
        restart_pending=restart_pending(settings),
        env_only=list(ENV_ONLY_KEYS),
        system=SystemInfoOut(
            **collect_system_info(
                host=settings.host,
                port=settings.port,
                web_origin=settings.web_origin,
            ),
        ),
    )


def server_logs_response(state: AppState, lines: int) -> ServerLogsOut:
    from openrecognition.logging_config import tail_log

    path, rows = tail_log(state.settings, lines)
    return ServerLogsOut(
        path=str(path),
        level=state.settings.log_level,
        file_enabled=state.settings.log_to_file,
        lines=rows,
    )
