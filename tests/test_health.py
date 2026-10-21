def test_health_public(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_live(client):
    r = client.get("/health/live")
    assert r.status_code == 200


def test_health_ready(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert "models_loaded" in r.json()


def test_unauthorized_without_key(client):
    r = client.get("/v1/capabilities")
    assert r.status_code == 401
