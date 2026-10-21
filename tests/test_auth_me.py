"""GET /v1/auth/me — credential scopes and MCP tool visibility."""


def test_auth_me_api_key(client, auth_headers):
    r = client.get("/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["credential_type"] == "api_key"
    assert "admin" in body["scopes"]
    assert len(body["mcp_tools"]) == 9


def test_auth_me_recognize_only_key(client, auth_headers):
    created = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "mcp-read-test", "mcp_tools": ["list_enrollments"]},
    )
    assert created.status_code == 200
    key = created.json()["key"]
    assert created.json()["mcp_tools"]
    assert len(created.json()["mcp_tools"]) == 1

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {key}"})
    assert me.status_code == 200
    names = {t["name"] for t in me.json()["mcp_tools"]}
    assert names == {"list_enrollments"}
