"""MCP stdio server entrypoint."""

from __future__ import annotations

import os
import sys

_IMPORT_ERROR: BaseException | None = None

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    FastMCP = None  # type: ignore[misc, assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def mcp_available() -> bool:
    return FastMCP is not None


async def resolve_mcp_auth() -> dict | None:
    """Scopes for this MCP process: env override, else from GET /v1/auth/me."""
    from openrecognition.integrator.mcp.client import OpenRecognitionApiError, OpenRecognitionClient

    override = os.environ.get("OPENRECOGNITION_MCP_SCOPES", "").strip()
    if override:
        scopes = [s.strip() for s in override.split(",") if s.strip()]
        return {"scopes": scopes, "mcp_tools": []}

    client = OpenRecognitionClient.from_env()
    if not client.api_key:
        return None

    try:
        return await client.get_json("/v1/auth/me")  # type: ignore[return-value]
    except OpenRecognitionApiError as exc:
        if exc.status in (401, 403):
            print(
                f"openrecognition mcp: invalid API key ({exc.message})",
                file=sys.stderr,
            )
            return None
        raise


def run_stdio() -> None:
    if not mcp_available():
        raise SystemExit(
            "MCP support is not installed. Install with: pip install 'openrecognition[mcp]'"
        ) from _IMPORT_ERROR

    import anyio

    from openrecognition.integrator.mcp.build import build_mcp_server

    async def _main() -> None:
        me = await resolve_mcp_auth()
        scopes = (me or {}).get("scopes") or []
        allowlist = None
        if me and me.get("mcp_tools"):
            allowlist = [t["name"] for t in me["mcp_tools"]]
        if not scopes and not allowlist:
            print(
                "openrecognition mcp: set OPENRECOGNITION_API_KEY (with MCP tools/scopes) "
                "or OPENRECOGNITION_MCP_SCOPES",
                file=sys.stderr,
            )
        server = build_mcp_server(scopes, allowlist)
        await server.run_stdio_async()

    anyio.run(_main)
