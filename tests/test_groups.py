"""Access groups: roles, library limits, and enrollment rights."""

from tests.helpers import wav_bytes


def _groups(client, headers):
    response = client.get("/v1/auth/groups", headers=headers)
    assert response.status_code == 200
    return response.json()


def _by_role(client, headers, role: str):
    return next(group for group in _groups(client, headers) if group["grants_role"] == role)


def _login(client, username: str, password: str):
    client.app.state.app_state.login_limiter.reset()
    response = client.post(
        "/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response


def _logout(client):
    client.post("/v1/auth/logout")
    client.app.state.app_state.login_limiter.reset()


def test_system_groups_and_crud(client, auth_headers):
    names = {group["name"] for group in _groups(client, auth_headers)}
    assert {"Administrators", "Operators", "Viewers"} <= names

    admins = _by_role(client, auth_headers, "admin")
    assert admins["system"] is True
    assert admins["sso_name"] == "admin"
    assert "sso" not in admins["description"].lower()
    for group in _groups(client, auth_headers):
        if group["system"]:
            assert "sso" not in (group["description"] or "").lower()
    denied = client.delete(f"/v1/auth/groups/{admins['id']}", headers=auth_headers)
    assert denied.status_code == 400

    created = client.post(
        "/v1/auth/groups",
        headers=auth_headers,
        json={"name": "Pet sitters", "description": "Add photos", "sso_name": "pet-sitters"},
    )
    assert created.status_code == 200
    group = created.json()
    assert group["grants_role"] is None
    assert group["system"] is False

    duplicate = client.post(
        "/v1/auth/groups",
        headers=auth_headers,
        json={"name": "Other sitters", "sso_name": "pet-sitters"},
    )
    assert duplicate.status_code == 400

    patched = client.patch(
        f"/v1/auth/groups/{group['id']}",
        headers=auth_headers,
        json={"description": "Family pets", "sso_name": "family-pets"},
    )
    assert patched.status_code == 200
    assert patched.json()["sso_name"] == "family-pets"
    assert patched.json()["description"] == "Family pets"

    assert client.delete(f"/v1/auth/groups/{group['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/v1/auth/groups/{group['id']}", headers=auth_headers).status_code == 404


def test_administrators_membership_raises_role(client, auth_headers):
    created = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "group-raised", "password": "secret-pass", "role": "viewer"},
    )
    assert created.status_code == 200
    user = created.json()
    admins = _by_role(client, auth_headers, "admin")
    updated = client.put(
        f"/v1/auth/groups/{admins['id']}/members",
        headers=auth_headers,
        json={"user_ids": [user["id"]]},
    )
    assert updated.status_code == 200

    _login(client, "group-raised", "secret-pass")
    try:
        me = client.get("/v1/auth/me")
        assert me.status_code == 200
        body = me.json()
        assert body["role"] == "admin"
        assert "admin" in body["scopes"]
        assert any(group["name"] == "Administrators" for group in body["groups"])
        assert client.get("/v1/auth/users").status_code == 200
    finally:
        _logout(client)
        client.put(
            f"/v1/auth/groups/{admins['id']}/members",
            headers=auth_headers,
            json={"user_ids": []},
        )


def test_viewer_sees_only_granted_enrollments(client, auth_headers):
    pet = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "Group Milo"},
    )
    person = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "Group Ada"},
    )
    assert pet.status_code == 200
    assert person.status_code == 200
    pet_id = pet.json()["id"]
    person_id = person.json()["id"]

    viewer = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "group-viewer", "password": "secret-pass", "role": "viewer"},
    ).json()
    group = client.post(
        "/v1/auth/groups",
        headers=auth_headers,
        json={"name": "Milo access", "description": "One pet"},
    ).json()
    assert client.put(
        f"/v1/auth/groups/{group['id']}/members",
        headers=auth_headers,
        json={"user_ids": [viewer["id"]]},
    ).status_code == 200
    assigned = client.put(
        f"/v1/auth/groups/{group['id']}/enrollments",
        headers=auth_headers,
        json={
            "enrollments": [
                {"enrollment_id": pet_id, "can_add_samples": True, "can_manage": False},
            ]
        },
    )
    assert assigned.status_code == 200

    _login(client, "group-viewer", "secret-pass")
    try:
        me = client.get("/v1/auth/me").json()
        assert me["role"] == "viewer"
        assert me["library_limited"] is True
        listed = client.get("/v1/enrollments")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [pet_id]
        assert client.get(f"/v1/enrollments/{person_id}").status_code == 404

        added = client.post(
            f"/v1/enrollments/{pet_id}/samples",
            files=[("files", ("clip.wav", wav_bytes(), "audio/wav"))],
        )
        assert added.status_code == 200
        denied = client.patch(
            f"/v1/enrollments/{pet_id}",
            json={"enabled": False},
        )
        assert denied.status_code == 403
        assert client.delete(f"/v1/enrollments/{pet_id}").status_code == 403
        overview = client.get("/v1/console/overview")
        assert overview.status_code == 200
        assert [row["id"] for row in overview.json()["enrollments"]] == [pet_id]
    finally:
        _logout(client)

    managed = client.put(
        f"/v1/auth/groups/{group['id']}/enrollments",
        headers=auth_headers,
        json={
            "enrollments": [
                {"enrollment_id": pet_id, "can_add_samples": True, "can_manage": True},
            ]
        },
    )
    assert managed.status_code == 200
    _login(client, "group-viewer", "secret-pass")
    try:
        patched = client.patch(f"/v1/enrollments/{pet_id}", json={"label": "Milo updated"})
        assert patched.status_code == 200
        assert patched.json()["label"] == "Milo updated"
    finally:
        _logout(client)


def test_operator_sees_only_enrollments_they_created(client, auth_headers):
    hidden = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "pet", "label": "Hidden From Operator"},
    )
    assert hidden.status_code == 200
    hidden_id = hidden.json()["id"]
    created = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "group-operator", "password": "secret-pass", "role": "operator"},
    )
    assert created.status_code == 200
    operator = created.json()
    _login(client, "group-operator", "secret-pass")
    try:
        mine = client.post(
            "/v1/enrollments",
            data={"type": "person", "label": "Operator Own"},
        )
        assert mine.status_code == 200
        mine_id = mine.json()["id"]
        listed = client.get("/v1/enrollments")
        assert listed.status_code == 200
        assert {row["id"] for row in listed.json()} == {mine_id}
        assert client.get(f"/v1/enrollments/{hidden_id}").status_code == 404
        assert client.delete(f"/v1/enrollments/{hidden_id}").status_code == 404
        me = client.get("/v1/auth/me").json()
        assert me["library_limited"] is True
        assert me["role"] == "operator"
    finally:
        _logout(client)

    admin_ids = {row["id"] for row in client.get("/v1/enrollments", headers=auth_headers).json()}
    assert hidden_id in admin_ids
    assert mine_id in admin_ids

    group = client.post(
        "/v1/auth/groups",
        headers=auth_headers,
        json={"name": "Share with operator", "description": "One extra name"},
    ).json()
    client.put(
        f"/v1/auth/groups/{group['id']}/members",
        headers=auth_headers,
        json={"user_ids": [operator["id"]]},
    )
    client.put(
        f"/v1/auth/groups/{group['id']}/enrollments",
        headers=auth_headers,
        json={
            "enrollments": [
                {"enrollment_id": hidden_id, "can_add_samples": True, "can_manage": False},
            ]
        },
    )
    _login(client, "group-operator", "secret-pass")
    try:
        ids = {row["id"] for row in client.get("/v1/enrollments").json()}
        assert hidden_id in ids
        assert mine_id in ids
        assert client.delete(f"/v1/enrollments/{hidden_id}").status_code == 403
    finally:
        _logout(client)


def test_cannot_remove_last_effective_admin(client, auth_headers):
    users = client.get("/v1/auth/users", headers=auth_headers).json()
    admin = next(user for user in users if user["username"] == "admin")
    created = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "group-last-admin", "password": "secret-pass", "role": "viewer"},
    )
    assert created.status_code == 200
    raised = created.json()
    admins = _by_role(client, auth_headers, "admin")

    added = client.put(
        f"/v1/auth/groups/{admins['id']}/members",
        headers=auth_headers,
        json={"user_ids": [raised["id"]]},
    )
    assert added.status_code == 200
    demoted = client.patch(
        f"/v1/auth/users/{admin['id']}",
        headers=auth_headers,
        json={"role": "viewer"},
    )
    assert demoted.status_code == 200
    try:
        emptied = client.put(
            f"/v1/auth/groups/{admins['id']}/members",
            headers=auth_headers,
            json={"user_ids": []},
        )
        assert emptied.status_code == 400
        removed = client.delete(f"/v1/auth/users/{raised['id']}", headers=auth_headers)
        assert removed.status_code == 400
    finally:
        client.patch(
            f"/v1/auth/users/{admin['id']}",
            headers=auth_headers,
            json={"role": "admin"},
        )
        client.put(
            f"/v1/auth/groups/{admins['id']}/members",
            headers=auth_headers,
            json={"user_ids": []},
        )
