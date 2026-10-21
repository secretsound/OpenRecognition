"""Build a scope-filtered FastMCP server instance."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from openrecognition.integrator.mcp import handlers
from openrecognition.integrator.mcp.catalog import MCP_RESOURCES, MCP_TOOLS
from openrecognition.integrator.mcp.client import OpenRecognitionClient
from openrecognition.integrator.mcp.scopes import (
    resolve_mcp_resources,
    resolve_mcp_tools,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore[misc, assignment]


def _bind_client(fn: Callable[..., Any], client: OpenRecognitionClient) -> Callable[..., Any]:
    """Wrap a handler so the MCP tool only receives user-visible parameters."""

    sig = inspect.signature(fn)
    params = [p for p in sig.parameters.values() if p.name != "client"]

    async def wrapper(*args: Any, **kwargs: Any) -> str:
        bound = sig.bind(client, *args, **kwargs)
        bound.apply_defaults()
        return await fn(*bound.args, **bound.kwargs)

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    wrapper.__signature__ = sig.replace(parameters=params)  # type: ignore[attr-defined]
    return wrapper


def build_mcp_server(
    granted_scopes: list[str],
    tool_allowlist: list[str] | None = None,
) -> FastMCP:
    if FastMCP is None:
        raise RuntimeError("MCP package not installed")

    client = OpenRecognitionClient.from_env()
    tool_metas = resolve_mcp_tools(granted_scopes, tool_allowlist)
    allowed_tools = {t["name"] for t in tool_metas}
    allowed_resources = {r["uri"] for r in resolve_mcp_resources(tool_metas)}

    mcp = FastMCP(
        "openrecognition",
        instructions=(
            "OpenRecognition MCP bridge. Tools call the local REST API; "
            "only tools allowed by this API key's scopes are exposed. "
            "Keep openrecognition serve running."
        ),
    )

    tool_map: dict[str, Callable[..., Any]] = {
        "get_health": handlers.get_health,
        "get_capabilities": handlers.get_capabilities,
        "list_enrollments": handlers.list_enrollments,
        "get_presence": handlers.get_presence,
        "audio_gate": handlers.audio_gate,
        "recognize_audio": handlers.recognize_audio,
        "recognize_image": handlers.recognize_image,
        "recognize_image_url": handlers.recognize_image_url,
        "enroll_from_paths": handlers.enroll_from_paths,
    }

    for meta in MCP_TOOLS:
        name = meta["name"]
        if name not in allowed_tools:
            continue
        fn = tool_map[name]
        mcp.add_tool(
            _bind_client(fn, client),
            name=name,
            description=meta["description"],
        )

    resource_map: dict[str, Callable[..., Any]] = {
        "openrecognition://health": handlers.resource_health,
        "openrecognition://capabilities": handlers.resource_capabilities,
        "openrecognition://enrollments": handlers.resource_enrollments,
    }

    for meta in MCP_RESOURCES:
        uri = meta["uri"]
        if uri not in allowed_resources:
            continue
        fn = resource_map[uri]
        mcp.resource(uri, name=meta["name"], description=meta["description"])(
            _bind_client(fn, client)
        )

    if not allowed_tools and not allowed_resources:

        async def _no_access() -> str:
            return (
                "This API key has no MCP tool scopes. Grant read, recognize, and/or enroll "
                "(or admin) on the key used in OPENRECOGNITION_API_KEY."
            )

        mcp.add_tool(
            _no_access,
            name="scope_required",
            description="Placeholder when the API key has no MCP scopes.",
        )

    return mcp
