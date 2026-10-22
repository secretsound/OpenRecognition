"""Saved server settings applied before bind and before models are opened."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from openrecognition.config import Settings
from openrecognition.runtime_settings import RuntimeSettingsStore

logger = logging.getLogger(__name__)

LANGUAGES = frozenset({"en", "es", "fr", "de", "pt", "zh"})
LOG_LEVELS = frozenset({"debug", "info", "warning", "error"})
SSO_PROTOCOLS = frozenset({"oidc", "saml"})
SSO_ROLES = frozenset({"viewer", "operator", "admin"})

RESTART_KEYS = (
    "host",
    "port",
    "http_enabled",
    "https_enabled",
    "https_port",
    "tls_cert_file",
    "tls_key_file",
    "models_dir",
    "model_packs_dir",
)

ENV_ONLY_KEYS = (
    "data_dir",
    "auth_required",
    "web_enabled",
    "docs_enabled",
    "web_origin",
)

_BOOL_KEYS = (
    "behind_proxy",
    "http_enabled",
    "https_enabled",
    "log_to_file",
    "health_detail_public",
    "sso_enabled",
    "sso_auto_provision",
    "sso_link_existing",
)
_INT_KEYS = ("port", "https_port")
_LIMITS = {
    "auth_rate_limit_per_minute": (1, 10_000),
    "log_max_mb": (1, 200),
    "log_backup_count": (1, 30),
    "video_max_upload_bytes": (1024 * 1024, 2 * 1024 * 1024 * 1024),
}
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_PATH_KEYS = ("models_dir", "model_packs_dir")
_STR_KEYS = (
    "public_url",
    "trusted_proxies",
    "display_language",
    "display_timezone",
    "host",
    "metrics_token",
    "tls_cert_file",
    "tls_key_file",
    "logs_dir",
    "log_level",
    "sso_protocol",
    "sso_label",
    "sso_default_role",
    "sso_username_claim",
    "oidc_issuer",
    "oidc_client_id",
    "oidc_client_secret",
    "oidc_scopes",
    "oidc_groups_claim",
    "saml_idp_entity_id",
    "saml_idp_sso_url",
    "saml_idp_x509_cert",
    "saml_sp_entity_id",
    "saml_username_attr",
    "saml_groups_attr",
)

_boot: dict[str, str] | None = None


def site_snapshot(settings: Settings) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key in _BOOL_KEYS:
        data[key] = bool(getattr(settings, key))
    for key in _INT_KEYS:
        data[key] = int(getattr(settings, key))
    for key in _LIMITS:
        data[key] = int(getattr(settings, key))
    for key in _PATH_KEYS:
        data[key] = str(getattr(settings, key))
    for key in _STR_KEYS:
        data[key] = str(getattr(settings, key) or "")
    return data


def valid_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def valid_metrics_token(value: str) -> bool:
    return bool(_TOKEN.fullmatch(value))


def _assign_choice(settings: Settings, key: str, value: str, allowed: frozenset[str]) -> None:
    cleaned = value.strip().lower() if key != "sso_default_role" else value.strip()
    if cleaned not in allowed:
        logger.warning("Ignoring saved %s", key)
        return
    setattr(settings, key, cleaned)


def apply_site_snapshot(settings: Settings, data: dict[str, Any]) -> None:
    """Apply a saved snapshot. Invalid values are skipped so a bad save cannot block startup."""
    if not data:
        return
    for key in _BOOL_KEYS:
        if key in data:
            setattr(settings, key, bool(data[key]))
    for key in _INT_KEYS:
        if key not in data:
            continue
        try:
            value = int(data[key])
        except (TypeError, ValueError):
            logger.warning("Ignoring saved %s", key)
            continue
        if 1 <= value <= 65535:
            setattr(settings, key, value)
    for key, (low, high) in _LIMITS.items():
        if key not in data:
            continue
        try:
            value = int(data[key])
        except (TypeError, ValueError):
            logger.warning("Ignoring saved %s", key)
            continue
        if low <= value <= high:
            setattr(settings, key, value)
        else:
            logger.warning("Ignoring saved %s", key)
    for key in _PATH_KEYS:
        if key not in data:
            continue
        raw = str(data[key] or "").strip()
        if not raw or "\x00" in raw or "\n" in raw:
            continue
        setattr(settings, key, Path(raw).expanduser())
    for key in _STR_KEYS:
        if key in ("host",):
            continue
        if key not in data or data[key] is None:
            continue
        value = str(data[key])
        if key == "log_level":
            _assign_choice(settings, key, value, LOG_LEVELS)
        elif key == "display_language":
            _assign_choice(settings, key, value, LANGUAGES)
        elif key == "display_timezone":
            zone = value.strip() or "UTC"
            if valid_timezone(zone):
                settings.display_timezone = zone
            else:
                logger.warning("Ignoring saved display_timezone")
        elif key == "metrics_token":
            token = value.strip()
            if not token or valid_metrics_token(token):
                settings.metrics_token = token
            else:
                logger.warning("Ignoring saved metrics token")
        elif key == "sso_protocol":
            _assign_choice(settings, key, value, SSO_PROTOCOLS)
        elif key == "sso_default_role":
            _assign_choice(settings, key, value, SSO_ROLES)
        else:
            setattr(settings, key, value)
    if "host" in data:
        host = str(data["host"] or "").strip()
        if host and len(host) <= 255 and not any(char in host for char in " \t\r\n/\\"):
            settings.host = host


def apply_boot_overrides(settings: Settings) -> None:
    store = RuntimeSettingsStore(Path(settings.data_dir) / "runtime_settings.json")
    apply_site_snapshot(settings, store.load())


def _norm(settings: Settings, key: str) -> str:
    value = getattr(settings, key)
    if key in _PATH_KEYS or key in ("tls_cert_file", "tls_key_file"):
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return str(Path(text).expanduser().resolve())
        except OSError:
            return text
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value).strip()


def capture_boot_state(settings: Settings) -> None:
    global _boot
    _boot = {key: _norm(settings, key) for key in RESTART_KEYS}


def restart_pending(settings: Settings) -> list[str]:
    if _boot is None:
        return []
    return [key for key in RESTART_KEYS if _norm(settings, key) != _boot[key]]
