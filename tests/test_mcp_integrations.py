"""MCP integration API endpoint."""

from openrecognition.integrator.mcp.catalog import MCP_TOOLS


def test_integrations_mcp_endpoint(client, auth_headers):
    r = client.get("/v1/integrations/mcp", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["api_base_url"].startswith("http://")
    assert "tools" in body
    assert len(body["tools"]) == len(MCP_TOOLS)
    assert "host_config_json" in body
    assert "scope_groups" in body
    assert "enabled_tools" in body
    parsed = __import__("json").loads(body["host_config_json"])
    assert "openrecognition" in parsed["mcpServers"]
    assert parsed["mcpServers"]["openrecognition"]["args"] == ["mcp"]
    assert "<api-key>" in body["host_config_json"]


def test_integrations_overview_includes_mcp(client, auth_headers):
    r = client.get("/v1/integrations", headers=auth_headers)
    assert r.status_code == 200
    assert "mcp" in r.json()
