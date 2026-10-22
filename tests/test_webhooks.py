from openrecognition.integrator.webhooks import render_template, render_webhook_body


def test_webhook_subscription(client, auth_headers):
    r = client.post(
        "/v1/webhooks/subscriptions",
        headers=auth_headers,
        json={
            "url": "http://127.0.0.1:9999/hook",
            "events": ["recognition.match"],
            "debounce_seconds": 5,
            "filters": {},
        },
    )
    assert r.status_code == 200
    body = r.json()
    wid = body["id"]
    assert body["title_template"]
    assert body["message_template"]
    assert body["include_details"] is True
    r2 = client.get("/v1/webhooks/subscriptions", headers=auth_headers)
    assert any(s["id"] == wid for s in r2.json())
    client.delete(f"/v1/webhooks/subscriptions/{wid}", headers=auth_headers)


def test_webhook_patch_templates(client, auth_headers):
    created = client.post(
        "/v1/integrations/webhooks",
        headers=auth_headers,
        json={
            "url": "http://127.0.0.1:9999/hook",
            "name": "Kitchen",
            "title_template": "{{label}} arrived",
            "message_template": "{{label}} at {{confidence}}",
            "events": ["recognition.match", "recognition.unknown"],
            "debounce_seconds": 15,
            "include_details": True,
        },
    )
    assert created.status_code == 200
    wid = created.json()["id"]
    assert created.json()["name"] == "Kitchen"

    patched = client.patch(
        f"/v1/integrations/webhooks/{wid}",
        headers=auth_headers,
        json={
            "title_template": "{{event_label}}: {{label}}",
            "include_details": False,
            "debounce_seconds": 45,
        },
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["title_template"] == "{{event_label}}: {{label}}"
    assert body["message_template"] == "{{label}} at {{confidence}}"
    assert body["include_details"] is False
    assert body["debounce_seconds"] == 45
    assert body["name"] == "Kitchen"
    client.delete(f"/v1/integrations/webhooks/{wid}", headers=auth_headers)


def test_render_template_double_and_single_braces():
    context = {"label": "Alex", "confidence": "92%"}
    assert render_template("{{label}} was recognized", context) == "Alex was recognized"
    assert render_template("{label} at {confidence}", context) == "Alex at 92%"
    assert render_template("{{missing}}", context) == ""


def test_webhook_body_templates():
    body = render_webhook_body(
        {
            "title_template": "{{label}} at the {{camera}}",
            "message_template": "{{event_label}} · {{confidence}}",
            "include_details": True,
        },
        "recognition.match",
        {
            "entities": [
                {
                    "label": "Alex",
                    "confidence": 0.92,
                    "type": "person",
                    "modality": "audio",
                    "entity_id": "e1",
                }
            ],
            "meta": {"camera_id": "front-door", "zone": "porch"},
            "mode": "identify",
            "gate": "accept",
            "scores": {"speech": 0.9},
        },
    )
    assert body["title"] == "Alex at the front-door"
    assert body["message"] == "Someone matched · 92%"
    assert body["event"] == "recognition.match"
    assert body["details"]["mode"] == "identify"
    assert body["details"]["confidence"] == 0.92
    assert body["details"]["camera_id"] == "front-door"
    assert body["details"]["scores"]["speech"] == 0.9


def test_webhook_body_wyoming_payload_and_optional_details():
    body = render_webhook_body(
        {
            "title_template": "{{label}}",
            "message_template": "{{transcript}}",
            "include_details": False,
        },
        "recognition.match",
        {
            "label": "Alex",
            "confidence": 0.8,
            "enrollment_id": "e1",
            "accepted": True,
            "transcript": "hello",
            "scores": {"speech": 0.99},
        },
    )
    assert body["title"] == "Alex"
    assert body["message"] == "hello"
    assert "details" not in body
