def test_users_crud(client, auth_headers):
    r = client.get("/v1/auth/users", headers=auth_headers)
    assert r.status_code == 200
    assert any(u["username"] == "admin" for u in r.json())

    r2 = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "operator1", "password": "secret123", "role": "operator"},
    )
    assert r2.status_code == 200
    uid = r2.json()["id"]
    assert r2.json()["role"] == "operator"

    r3 = client.patch(
        f"/v1/auth/users/{uid}",
        headers=auth_headers,
        json={"role": "viewer"},
    )
    assert r3.status_code == 200
    assert r3.json()["role"] == "viewer"

    r4 = client.delete(f"/v1/auth/users/{uid}", headers=auth_headers)
    assert r4.status_code == 204


def test_cannot_duplicate_username(client, auth_headers):
    client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "dupuser", "password": "x", "role": "viewer"},
    )
    r = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "dupuser", "password": "y", "role": "viewer"},
    )
    assert r.status_code == 400


def test_email_sign_in_and_sso_link(client, auth_headers):
    created = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={
            "username": "mailer",
            "password": "secret123",
            "role": "operator",
            "email": "Mailer@Example.com",
        },
    )
    assert created.status_code == 200
    assert created.json()["email"] == "mailer@example.com"

    duplicate = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={
            "username": "mailer2",
            "password": "secret123",
            "role": "viewer",
            "email": "mailer@example.com",
        },
    )
    assert duplicate.status_code == 400

    signed_in = client.post(
        "/v1/auth/login",
        json={"username": "MAILER@example.com", "password": "secret123"},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["username"] == "mailer"

    cleared = client.patch(
        f"/v1/auth/users/{created.json()['id']}",
        headers=auth_headers,
        json={"email": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["email"] is None

    client.app.state.app_state.sessions.update_user(
        created.json()["id"], email="mailer@example.com", email_set=True
    )
    sessions = client.app.state.app_state.sessions
    try:
        sessions.provision_sso_user(
            username="mailer-from-idp",
            subject="oidc-sub-mailer",
            protocol="oidc",
            role="viewer",
            link_existing=True,
            auto_provision=False,
            email="Mailer@Example.com",
            match="username",
        )
        raise AssertionError("username matching should not use the email")
    except ValueError:
        pass
    linked = sessions.provision_sso_user(
        username="mailer-from-idp",
        subject="oidc-sub-mailer",
        protocol="oidc",
        role="viewer",
        link_existing=True,
        auto_provision=False,
        email="Mailer@Example.com",
        match="email",
    )
    assert linked["username"] == "mailer"
    assert linked["id"] == created.json()["id"]
