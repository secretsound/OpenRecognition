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
