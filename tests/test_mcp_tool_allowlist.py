"""API key permissions cover the REST API and MCP tools together."""

from openrecognition.integrator.mcp.scopes import (
    normalize_key_scopes,
    resolve_mcp_resources,
    resolve_mcp_tools,
    scopes_from_tool_names,
    validate_mcp_tools_fit_rest_scopes,
)


def test_normalize_collapses_admin_and_orders_scopes():
    assert normalize_key_scopes(["delete", "enroll", "read", "update"]) == [
        "read",
        "enroll",
        "update",
        "delete",
    ]
    assert normalize_key_scopes(["read", "admin"]) == ["admin"]


def test_normalize_rejects_unknown_or_empty():
    try:
        normalize_key_scopes(["write"])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "write" in str(exc)
    try:
        normalize_key_scopes([])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "at least one" in str(exc).lower()


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


def test_scopes_grant_matching_api_and_mcp(client, auth_headers):
    r = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "recognize-key", "scopes": ["recognize"], "mcp_tools": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scopes"] == ["recognize"]
    assert body["mcp_tool_allowlist"] is None
    names = {t["name"] for t in body["mcp_tools"]}
    assert "recognize_audio" in names
    assert "audio_gate" in names
    assert "get_health" not in names
    assert "enroll_from_paths" not in names

    me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {body['key']}"},
    )
    assert {t["name"] for t in me.json()["mcp_tools"]} == names
    denied = client.get("/v1/enrollments", headers={"Authorization": f"Bearer {body['key']}"})
    assert denied.status_code == 403


def test_explicit_scopes_win_over_legacy_tool_list(client, auth_headers):
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
    assert body["scopes"] == ["read", "recognize"]
    names = {t["name"] for t in body["mcp_tools"]}
    assert "get_health" in names
    assert "recognize_audio" in names
    assert "enroll_from_paths" not in names


def test_legacy_tool_names_expand_to_permissions(client, auth_headers):
    r = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "finite-mcp", "mcp_tools": ["get_health", "audio_gate"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scopes"] == ["read", "recognize"]
    names = {t["name"] for t in body["mcp_tools"]}
    assert "get_health" in names
    assert "list_enrollments" in names
    assert "audio_gate" in names
    assert "recognize_image" in names

    me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {body['key']}"},
    )
    assert {t["name"] for t in me.json()["mcp_tools"]} == names


def test_update_key_name_and_permissions(client, auth_headers):
    created = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "door", "scopes": ["recognize"]},
    )
    assert created.status_code == 200
    body = created.json()
    key = body["key"]
    kid = body["id"]

    updated = client.patch(
        f"/v1/auth/keys/{kid}",
        headers=auth_headers,
        json={"name": "front-door", "scopes": ["read", "enroll"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "front-door"
    assert updated.json()["scopes"] == ["read", "enroll"]

    listed = client.get("/v1/auth/keys", headers=auth_headers)
    row = next(item for item in listed.json() if item["id"] == kid)
    assert row["name"] == "front-door"
    assert row["scopes"] == ["read", "enroll"]

    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {key}"})
    names = {t["name"] for t in me.json()["mcp_tools"]}
    assert "list_enrollments" in names
    assert "enroll_from_paths" in names
    assert "recognize_audio" not in names

    missing = client.patch(
        "/v1/auth/keys/missing",
        headers=auth_headers,
        json={"name": "nope"},
    )
    assert missing.status_code == 404

    empty = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "empty", "scopes": []},
    )
    assert empty.status_code == 400


def _person(client, auth_headers, label: str) -> str:
    created = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": label},
    )
    assert created.status_code == 200
    return created.json()["id"]


def _key(client, auth_headers, name: str, scopes: list[str]) -> dict:
    created = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": name, "scopes": scopes},
    )
    assert created.status_code == 200
    return {"Authorization": f"Bearer {created.json()['key']}"}


def test_update_permission_changes_existing_profiles(client, auth_headers):
    eid = _person(client, auth_headers, "Ada")
    adder = _key(client, auth_headers, "adder", ["enroll"])
    updater = _key(client, auth_headers, "updater", ["update"])

    denied = client.patch(f"/v1/enrollments/{eid}", headers=adder, json={"label": "Nope"})
    assert denied.status_code == 403

    renamed = client.patch(f"/v1/enrollments/{eid}", headers=updater, json={"label": "Ada 2"})
    assert renamed.status_code == 200
    assert renamed.json()["label"] == "Ada 2"


def test_delete_permission_removes_profiles(client, auth_headers):
    eid = _person(client, auth_headers, "Bea")
    adder = _key(client, auth_headers, "adder-only", ["enroll"])
    remover = _key(client, auth_headers, "remover", ["delete"])

    denied = client.delete(f"/v1/enrollments/{eid}", headers=adder)
    assert denied.status_code == 403
    assert client.get(f"/v1/enrollments/{eid}", headers=auth_headers).status_code == 200

    removed = client.delete(f"/v1/enrollments/{eid}", headers=remover)
    assert removed.status_code == 204
    assert client.get(f"/v1/enrollments/{eid}", headers=auth_headers).status_code == 404
