"""Map API key scopes to MCP tools and resources."""

from __future__ import annotations

from openrecognition.integrator.mcp.catalog import (
    MCP_RESOURCES,
    MCP_TOOLS,
    McpResourceMeta,
    McpToolMeta,
)

API_SCOPES = frozenset({"read", "recognize", "enroll", "admin"})

SCOPE_GROUPS: list[dict[str, str]] = [
    {
        "id": "read",
        "label": "Read",
        "description": "Health, capabilities, enrollments list, and presence.",
    },
    {
        "id": "recognize",
        "label": "Recognize",
        "description": "Audio gate, speaker ID, and image recognition tools.",
    },
    {
        "id": "enroll",
        "label": "Enroll",
        "description": "Create identities from local media files.",
    },
]


def allows(scope_required: str, granted: list[str]) -> bool:
    if "admin" in granted:
        return True
    return scope_required in granted


def filter_tools(granted: list[str]) -> list[McpToolMeta]:
    return [t for t in MCP_TOOLS if allows(t["scope"], granted)]


def filter_resources(granted: list[str]) -> list[McpResourceMeta]:
    return [r for r in MCP_RESOURCES if allows(r["scope"], granted)]


def tool_names(granted: list[str]) -> list[str]:
    return [t["name"] for t in filter_tools(granted)]


def resource_uris(granted: list[str]) -> list[str]:
    return [r["uri"] for r in filter_resources(granted)]


# MCP resources map 1:1 to a tool that must be enabled
RESOURCE_TOOL: dict[str, str] = {
    "openrecognition://health": "get_health",
    "openrecognition://capabilities": "get_capabilities",
    "openrecognition://enrollments": "list_enrollments",
}

KNOWN_TOOL_NAMES = frozenset(t["name"] for t in MCP_TOOLS)


def validate_mcp_tool_names(names: list[str]) -> list[str]:
    unknown = [n for n in names if n not in KNOWN_TOOL_NAMES]
    if unknown:
        raise ValueError(f"Unknown MCP tools: {', '.join(unknown)}")
    return names


def scopes_from_tool_names(tool_names: list[str]) -> list[str]:
    """Minimal REST scopes required for the selected MCP tools."""
    scopes: set[str] = set()
    by_name = {t["name"]: t for t in MCP_TOOLS}
    for name in tool_names:
        scopes.add(by_name[name]["scope"])
    return sorted(scopes)


def resolve_mcp_tools(
    scopes: list[str],
    tool_allowlist: list[str] | None,
) -> list[McpToolMeta]:
    """Tools exposed to MCP for this credential.

    ``tool_allowlist``:
    - ``None`` — all tools permitted by REST scopes (legacy / REST-only keys)
    - ``[]`` — MCP explicitly disabled
    - non-empty — only listed tools (must fit REST scopes)
    """
    pool = filter_tools(scopes)
    if tool_allowlist is None:
        return pool
    if len(tool_allowlist) == 0:
        return []
    allowed = set(tool_allowlist)
    return [t for t in pool if t["name"] in allowed]


def validate_mcp_tools_fit_rest_scopes(
    tool_names: list[str],
    rest_scopes: list[str],
) -> None:
    """Raise ValueError if an MCP tool needs a REST scope the key does not have."""
    by_name = {t["name"]: t for t in MCP_TOOLS}
    for name in tool_names:
        required = by_name[name]["scope"]
        if not allows(required, rest_scopes):
            raise ValueError(
                f"MCP tool '{name}' requires REST scope '{required}' on this key"
            )


def resolve_mcp_resources(tools: list[McpToolMeta]) -> list[McpResourceMeta]:
    enabled = {t["name"] for t in tools}
    return [
        r
        for r in MCP_RESOURCES
        if RESOURCE_TOOL.get(r["uri"]) in enabled
    ]
