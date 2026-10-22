def test_integrations_overview(client, auth_headers):
    r = client.get("/v1/integrations", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "mqtt" in body
    assert "wyoming" in body
    assert "mcp" in body
    assert "webhooks" in body
    assert isinstance(body["webhooks"], list)


def test_mqtt_integration(client, auth_headers):
    r = client.get("/v1/integrations/mqtt", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert body["password_set"] is False
    assert "password" not in body
    assert body["username"] == ""
    assert body["client_id"] == "openrecognition"
    assert body["use_tls"] is False
    assert body["qos"] == 0
    assert body["retain"] is True

    r2 = client.patch(
        "/v1/integrations/mqtt",
        headers=auth_headers,
        json={
            "enabled": False,
            "host": "mqtt.local",
            "port": 1884,
            "topic_prefix": "or",
            "username": "ha",
            "password": "secret-pass",
            "client_id": "or-kitchen",
            "use_tls": True,
            "tls_insecure": True,
            "qos": 1,
            "retain": False,
        },
    )
    assert r2.status_code == 200
    saved = r2.json()
    assert saved["host"] == "mqtt.local"
    assert saved["port"] == 1884
    assert saved["username"] == "ha"
    assert saved["password_set"] is True
    assert "password" not in saved
    assert saved["client_id"] == "or-kitchen"
    assert saved["use_tls"] is True
    assert saved["tls_insecure"] is True
    assert saved["qos"] == 1
    assert saved["retain"] is False

    kept = client.patch(
        "/v1/integrations/mqtt",
        headers=auth_headers,
        json={"username": "ha2"},
    )
    assert kept.status_code == 200
    assert kept.json()["username"] == "ha2"
    assert kept.json()["password_set"] is True

    cleared = client.patch(
        "/v1/integrations/mqtt",
        headers=auth_headers,
        json={"password": ""},
    )
    assert cleared.json()["password_set"] is False

    client.patch(
        "/v1/integrations/mqtt",
        headers=auth_headers,
        json={
            "enabled": False,
            "host": "localhost",
            "port": 1883,
            "topic_prefix": "openrecognition",
            "username": "",
            "client_id": "openrecognition",
            "use_tls": False,
            "tls_insecure": False,
            "qos": 0,
            "retain": True,
        },
    )


def test_mqtt_test_connection_reports_failure(client, auth_headers):
    r = client.post(
        "/v1/integrations/mqtt/test",
        headers=auth_headers,
        json={"host": "127.0.0.1", "port": 1, "username": "ha", "password": "nope"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["message"]


def test_webhook_integration(client, auth_headers):
    r = client.post(
        "/v1/integrations/webhooks",
        headers=auth_headers,
        json={
            "url": "http://127.0.0.1:9999/hook",
            "events": ["recognition.match"],
            "debounce_seconds": 5,
            "filters": {},
        },
    )
    assert r.status_code == 200
    wid = r.json()["id"]

    listed = client.get("/v1/integrations/webhooks", headers=auth_headers)
    assert any(s["id"] == wid for s in listed.json())

    client.delete(f"/v1/integrations/webhooks/{wid}", headers=auth_headers)


def test_wyoming_integration(client, auth_headers):
    r = client.get("/v1/integrations/wyoming", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert "uri" in body
    assert "upstream_uri" in body
    assert body["require_speaker_match"] is False
    assert body["block_on_gate_reject"] is False
    assert body["tag_speaker"] is True
    assert body["include_confidence"] is True
    assert body["include_candidates"] is False

    r2 = client.patch(
        "/v1/integrations/wyoming",
        headers=auth_headers,
        json={
            "enabled": False,
            "uri": "tcp://0.0.0.0:10300",
            "upstream_uri": "tcp://127.0.0.1:10301",
            "min_confidence": 0.8,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["min_confidence"] == 0.8

    toggles = client.patch(
        "/v1/integrations/wyoming",
        headers=auth_headers,
        json={
            "tag_speaker": True,
            "include_confidence": True,
            "include_candidates": True,
        },
    )
    assert toggles.status_code == 200
    assert toggles.json()["tag_speaker"] is True
    assert toggles.json()["include_confidence"] is True
    assert toggles.json()["include_candidates"] is True
