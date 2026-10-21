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
    assert "enabled" in r.json()

    r2 = client.patch(
        "/v1/integrations/mqtt",
        headers=auth_headers,
        json={"enabled": False, "host": "mqtt.local", "port": 1884, "topic_prefix": "or"},
    )
    assert r2.status_code == 200
    assert r2.json()["host"] == "mqtt.local"
    assert r2.json()["port"] == 1884

    client.patch(
        "/v1/integrations/mqtt",
        headers=auth_headers,
        json={"enabled": False, "host": "localhost", "port": 1883, "topic_prefix": "openrecognition"},
    )


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
