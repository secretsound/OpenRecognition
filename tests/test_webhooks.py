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
    wid = r.json()["id"]
    r2 = client.get("/v1/webhooks/subscriptions", headers=auth_headers)
    assert any(s["id"] == wid for s in r2.json())
