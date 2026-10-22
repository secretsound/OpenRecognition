"""GET /v1/auth/me — credential scopes and MCP tool visibility."""


def test_auth_me_api_key(client, auth_headers):
    r = client.get("/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["credential_type"] == "api_key"
    assert "admin" in body["scopes"]
    assert body["role"] == "admin"
    assert len(body["mcp_tools"]) == 9


def test_auth_me_read_key_exposes_every_read_tool(client, auth_headers):
    created = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "mcp-read-test", "scopes": ["read"]},
    )
    assert created.status_code == 200
    key = created.json()["key"]
    names = {t["name"] for t in created.json()["mcp_tools"]}
    assert names == {"get_health", "get_capabilities", "list_enrollments", "get_presence"}

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {key}"})
    assert me.status_code == 200
    assert {t["name"] for t in me.json()["mcp_tools"]} == names
    assert me.json()["role"] == "viewer"
