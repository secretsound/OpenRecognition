import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def lan_client(tmp_path):
    from openrecognition.config import settings

    previous = settings.data_dir
    settings.data_dir = tmp_path
    from openrecognition.api.app import create_app

    try:
        with TestClient(create_app(), base_url="http://192.168.23.128") as client:
            yield client
    finally:
        settings.data_dir = previous


def test_lan_http_login_cookie_is_not_secure(lan_client):
    created = lan_client.post(
        "/v1/auth/setup",
        json={"username": "ada", "password": "password123"},
    )
    assert created.status_code == 200
    lan_client.post("/v1/auth/logout")
    response = lan_client.post(
        "/v1/auth/login",
        json={"username": "ada", "password": "password123"},
    )
    assert response.status_code == 200
    assert "Secure" not in response.headers["set-cookie"]
    assert lan_client.get("/v1/capabilities").status_code == 200


def test_https_login_cookie_is_secure(tmp_path):
    from openrecognition.config import settings

    previous = settings.data_dir
    settings.data_dir = tmp_path / "https"
    from openrecognition.api.app import create_app

    try:
        with TestClient(create_app(), base_url="https://192.168.23.128") as https:
            https.post("/v1/auth/setup", json={"username": "ada", "password": "password123"})
            https.post("/v1/auth/logout")
            response = https.post(
                "/v1/auth/login",
                json={"username": "ada", "password": "password123"},
            )
            assert response.status_code == 200
            assert "Secure" in response.headers["set-cookie"]
    finally:
        settings.data_dir = previous


def test_setup_is_once_and_opens_a_session(lan_client):
    assert lan_client.get("/v1/auth/setup").json() == {"required": True}
    created = lan_client.post(
        "/v1/auth/setup",
        json={"username": "ada", "password": "correct-horse"},
    )
    assert created.status_code == 200
    assert created.json()["username"] == "ada"
    assert lan_client.get("/v1/capabilities").status_code == 200
    assert lan_client.get("/v1/auth/setup").json() == {"required": False}
    again = lan_client.post(
        "/v1/auth/setup",
        json={"username": "ada", "password": "correct-horse"},
    )
    assert again.status_code == 400
    assert not (lan_client.app.state.app_state.settings.data_dir / "admin.password").exists()
    assert not (lan_client.app.state.app_state.settings.data_dir / "bootstrap.key").exists()
