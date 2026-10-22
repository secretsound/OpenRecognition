from tests.helpers import wav_bytes


def test_console_overview_shape(client, auth_headers):
    r = client.get("/v1/console/overview", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["enrollments"], list)
    assert isinstance(body["ready_count"], int)
    assert isinstance(body["attention"], list)
    assert isinstance(body["recent_activity"], list)
    assert "last_seen" in body
    assert isinstance(body["has_recognition"], bool)
    assert "models_ready" in body
    assert "wyoming_enabled" in body
    assert body["webhook_count"] == 0
    assert body["hardware"] in ("pi", "mini", "desktop", "server")
    assert "/v1/console/overview" in client.get("/v1/capabilities", headers=auth_headers).json()[
        "endpoints"
    ]


def test_console_overview_includes_library_and_activity(client, auth_headers):
    created = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "Ada"},
        files=[("files", ("a.wav", wav_bytes(), "audio/wav"))],
    )
    assert created.status_code == 200
    eid = created.json()["id"]

    client.post(
        "/v1/recognize/audio?mode=identify&dry_run=true",
        headers=auth_headers,
        files={"file": ("test.wav", wav_bytes(), "audio/wav")},
    )

    state = client.app.state.app_state
    state.gallery.update_presence(eid, "Ada", "person", "audio", None, 0.91)

    r = client.get("/v1/console/overview", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert any(row["id"] == eid for row in body["enrollments"])
    assert body["has_recognition"] is True
    assert body["recent_activity"]
    assert body["last_seen"]["enrollment_id"] == eid
    assert body["last_seen"]["label"] == "Ada"


def test_enrollment_search(client, auth_headers):
    client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "Ada SearchProbe"},
    )
    client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "pet", "label": "Rex SearchProbe"},
    )

    listed = client.get("/v1/enrollments?q=searchprobe", headers=auth_headers)
    assert listed.status_code == 200
    names = [row["label"] for row in listed.json()]
    assert "Ada SearchProbe" in names
    assert "Rex SearchProbe" in names

    ada = client.get("/v1/enrollments?q=ada%20search", headers=auth_headers)
    assert [row["label"] for row in ada.json()] == ["Ada SearchProbe"]

    pets = client.get("/v1/enrollments?type=pet&q=searchprobe", headers=auth_headers)
    assert [row["label"] for row in pets.json()] == ["Rex SearchProbe"]

    missing = client.get("/v1/enrollments?q=nobody-searchprobe", headers=auth_headers)
    assert missing.json() == []
