"""Per-tool MCP allowlist on API keys."""

from openrecognition.integrator.mcp.scopes import (
    resolve_mcp_resources,
    resolve_mcp_tools,
    scopes_from_tool_names,
    validate_mcp_tools_fit_rest_scopes,
)


def test_allowlist_limits_tools():
    tools = resolve_mcp_tools(["read", "recognize"], ["get_health"])
    names = {t["name"] for t in tools}
    assert names == {"get_health"}


def test_empty_allowlist_disables_mcp():
    tools = resolve_mcp_tools(["read", "recognize"], [])
    assert tools == []


def test_null_allowlist_all_in_scope():
    tools = resolve_mcp_tools(["read"], None)
    assert len(tools) == 4


def test_scopes_derived_from_tools():
    assert scopes_from_tool_names(["audio_gate", "get_health"]) == ["read", "recognize"]


def test_resources_follow_allowlist():
    tools = resolve_mcp_tools(["read"], ["get_capabilities"])
    resources = resolve_mcp_resources(tools)
    assert len(resources) == 1
    assert resources[0]["uri"] == "openrecognition://capabilities"


def test_mcp_tool_requires_rest_scope():
    try:
        validate_mcp_tools_fit_rest_scopes(["recognize_audio"], ["read"])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "recognize" in str(exc)


def test_create_key_api_only(client, auth_headers):
    r = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "api-only", "scopes": ["recognize"], "mcp_tools": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scopes"] == ["recognize"]
    assert body["mcp_tool_allowlist"] == []
    assert body["mcp_tools"] == []

    me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {body['key']}"},
    )
    assert me.json()["mcp_tools"] == []


def test_create_key_both_sections(client, auth_headers):
    r = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={
            "name": "both",
            "scopes": ["read", "recognize"],
            "mcp_tools": ["get_health"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body["scopes"]) == {"read", "recognize"}
    assert {t["name"] for t in body["mcp_tools"]} == {"get_health"}


def test_create_key_with_mcp_tools(client, auth_headers):
    r = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "finite-mcp", "mcp_tools": ["get_health", "audio_gate"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert {t["name"] for t in body["mcp_tools"]} == {"get_health", "audio_gate"}
    assert set(body["scopes"]) == {"read", "recognize"}

    me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {body['key']}"},
    )
    assert {t["name"] for t in me.json()["mcp_tools"]} == {"get_health", "audio_gate"}
