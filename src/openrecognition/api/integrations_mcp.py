"""MCP integration metadata for API and web UI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from fastapi import Request

from openrecognition.integrator.mcp.catalog import MCP_RESOURCES, MCP_TOOLS, SUGGESTED_MCP_SCOPES
from openrecognition.integrator.mcp.scopes import (
    SCOPE_GROUPS,
    filter_resources,
    filter_tools,
)
from openrecognition.integrator.mcp.server import mcp_available

if TYPE_CHECKING:
    from openrecognition.app_state import AppState

HOST_CONFIG_HINTS = [
    {
        "host": "Claude Desktop",
        "config_path": "claude_desktop_config.json (see Anthropic MCP docs for OS path)",
    },
    {
        "host": "Cursor",
        "config_path": "~/.cursor/mcp.json or <workspace>/.cursor/mcp.json",
    },
    {
        "host": "VS Code (MCP extension)",
        "config_path": ".vscode/mcp.json in your workspace",
    },
    {
        "host": "Other MCP clients",
        "config_path": "Client-specific mcp.json / config — use the mcpServers block below",
    },
]


def public_api_base_url(state: AppState, request: Request | None = None) -> str:
    """Address an MCP client should call — never 0.0.0.0."""
    host = state.settings.host
    if host in ("0.0.0.0", "::", "[::]"):
        host = "127.0.0.1"
    configured = f"http://{host}:{state.settings.port}"
    if request is None:
        return configured
    req_host = request.headers.get("host", "")
    if not req_host or req_host.startswith("0.0.0.0") or req_host.startswith("[::]"):
        return configured
    # Browser-proxied Vite hosts are not the API. Keep the listen port.
    if ":" in req_host.rsplit("]", 1)[-1] and req_host.rsplit(":", 1)[-1] != str(state.settings.port):
        return configured
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{scheme}://{req_host}".rstrip("/")


def build_host_config_json(api_base_url: str, api_key_placeholder: str = "<api-key>") -> str:
    config = {
        "mcpServers": {
            "openrecognition": {
                "command": "openrecognition",
                "args": ["mcp"],
                "env": {
                    "OPENRECOGNITION_API_URL": api_base_url,
                    "OPENRECOGNITION_API_KEY": api_key_placeholder,
                },
            }
        }
    }
    return json.dumps(config, indent=2)


def mcp_settings_out(
    state: AppState,
    auth: dict[str, Any] | None = None,
    request: Request | None = None,
) -> dict:
    base = public_api_base_url(state, request)
    ready = state.pool.models_loaded
    available = mcp_available()
    granted = (auth or {}).get("scopes") or []

    enabled_tools = filter_tools(granted) if granted else list(MCP_TOOLS)
    enabled_resources = filter_resources(granted) if granted else list(MCP_RESOURCES)

    return {
        "available": available,
        "api_base_url": base,
        "server_ready": ready,
        "scope_groups": list(SCOPE_GROUPS),
        "suggested_scopes": list(SUGGESTED_MCP_SCOPES),
        "tools": list(MCP_TOOLS),
        "resources": list(MCP_RESOURCES),
        "enabled_tools": enabled_tools,
        "enabled_resources": enabled_resources,
        "host_config_json": build_host_config_json(base),
        "host_config_hints": HOST_CONFIG_HINTS,
        "install_hint": (
            "pip install 'openrecognition[mcp]'"
            if not available
            else None
        ),
    }
