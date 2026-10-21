import bcrypt

from openrecognition.auth.keys import ApiKeyService
from openrecognition.auth.sessions import SessionService
from openrecognition.gallery.db import Database


def test_api_key_lookup_is_by_hash(tmp_path):
    keys = ApiKeyService(Database(tmp_path / "openrecognition.db"))
    created = keys.create_key("door", ["read"])
    assert created["key"]
    row = keys.db.fetchone("SELECT key_hash FROM api_keys WHERE id = ?", (created["id"],))
    assert row["key_hash"].startswith("sha256:")
    assert keys.authenticate(created["key"])["name"] == "door"
    assert keys.authenticate("or_nope") is None


def test_legacy_bcrypt_key_upgrades_to_sha256(tmp_path):
    db = Database(tmp_path / "openrecognition.db")
    raw = "or_legacy_secret"
    digest = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
    db.execute(
        "INSERT INTO api_keys (id, name, key_hash, scopes, created_at) VALUES (?, ?, ?, ?, ?)",
        ("legacy", "old", digest, '["read"]', "2020-01-01T00:00:00+00:00"),
    )
    keys = ApiKeyService(db)
    assert keys.authenticate(raw)["name"] == "old"
    row = db.fetchone("SELECT key_hash FROM api_keys WHERE id = ?", ("legacy",))
    assert row["key_hash"].startswith("sha256:")
    assert keys.authenticate(raw)["id"] == "legacy"


def test_login_rate_limit_and_logout(client, auth_headers):
    state = client.app.state.app_state
    state.login_limiter.reset()
    previous = state.settings.auth_rate_limit_per_minute
    state.settings.auth_rate_limit_per_minute = 3
    try:
        created = client.post(
            "/v1/auth/users",
            headers=auth_headers,
            json={"username": "rate-op", "password": "secret-pass", "role": "operator"},
        )
        assert created.status_code == 200

        ok = client.post(
            "/v1/auth/login",
            json={"username": "rate-op", "password": "secret-pass"},
        )
        assert ok.status_code == 200
        sid = ok.json()["session_id"]
        assert client.get("/v1/auth/me").status_code == 200

        assert client.post("/v1/auth/logout").status_code == 200
        assert client.get("/v1/auth/me").status_code == 401
        denied = client.get("/v1/auth/me", headers={"X-Session-ID": sid})
        assert denied.status_code == 401

        for _ in range(2):
            bad = client.post(
                "/v1/auth/login",
                json={"username": "rate-op", "password": "wrong"},
            )
            assert bad.status_code == 401
        blocked = client.post(
            "/v1/auth/login",
            json={"username": "rate-op", "password": "secret-pass"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "RATE_LIMITED"
    finally:
        state.settings.auth_rate_limit_per_minute = previous
        state.login_limiter.reset()


def test_password_longer_than_bcrypt_limit_is_rejected(client, auth_headers):
    response = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={"username": "long-pw", "password": "x" * 80, "role": "viewer"},
    )
    assert response.status_code == 400
    assert "72" in response.json()["message"]


def test_session_service_rejects_overlong_login(tmp_path):
    sessions = SessionService(Database(tmp_path / "openrecognition.db"))
    password = sessions.ensure_default_admin(password="correct-horse")
    assert sessions.authenticate_user("admin", "x" * 80) is None
    assert sessions.authenticate_user("admin", password)
