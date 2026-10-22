def test_presence(client, auth_headers):
    r = client.get("/v1/presence", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_metrics(client, auth_headers):
    r = client.get("/metrics", headers=auth_headers)
    assert r.status_code == 200
    assert "openrecognition_info" in r.text


def test_admin_settings(client, auth_headers):
    r = client.get("/v1/admin/settings", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["hardware"]["effective"] in ("pi", "mini", "desktop", "server")
    assert body["models_dir"]
    assert "feature_flags" in body
    assert "system" in body
    assert body["system"]["python_version"]
    assert body["system"]["server_version"]

    r2 = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "maintenance_mode": True,
            "enrollment_media_retention": "keep",
            "feature_flags": {"biometrics.face_enabled": False},
        },
    )
    assert r2.status_code == 200
    assert r2.json()["maintenance_mode"] is True
    assert r2.json()["enrollment_media_retention"] == "keep"
    assert r2.json()["feature_flags"]["biometrics.face_enabled"] is False
    assert "default_min_confidence" in r2.json()
    assert "mqtt_host" in r2.json()

    r3 = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "default_min_confidence": 0.8,
            "session_ttl_minutes": 120,
            "recognition_log_retention_days": 30,
        },
    )
    assert r3.status_code == 200
    assert r3.json()["default_min_confidence"] == 0.8
    assert r3.json()["session_ttl_minutes"] == 120

    client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={
            "maintenance_mode": False,
            "enrollment_media_retention": "embeddings_only",
            "default_min_confidence": 0.75,
            "session_ttl_minutes": 60,
            "feature_flags": {"biometrics.face_enabled": True},
            "inference_backend": "heuristic",
        },
    )


def test_restart_service(client, auth_headers, monkeypatch):
    called = []

    def fake_schedule():
        called.append(True)

    monkeypatch.setattr(
        "openrecognition.api.routes.admin.schedule_restart",
        fake_schedule,
    )
    r = client.post("/v1/admin/restart", headers=auth_headers)
    assert r.status_code == 202
    assert r.json()["ok"] is True
    assert called


def test_maintenance(client, auth_headers):
    r = client.post("/v1/admin/maintenance?enabled=true", headers=auth_headers)
    assert r.status_code == 200
    r2 = client.post("/v1/admin/maintenance?enabled=false", headers=auth_headers)
    assert r2.status_code == 200


def test_recognition_logs(client, auth_headers):
    from tests.helpers import wav_bytes

    wav = wav_bytes()
    listed = client.get("/v1/admin/logs", headers=auth_headers)
    assert listed.status_code == 200
    assert "items" in listed.json()

    client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "log-test-user"},
        files=[("files", ("a.wav", wav, "audio/wav"))],
    )
    client.post(
        "/v1/recognize/audio?mode=identify&min_confidence=0.5&dry_run=true",
        headers=auth_headers,
        files={"file": ("t.wav", wav, "audio/wav")},
    )

    listed2 = client.get("/v1/admin/logs?limit=20", headers=auth_headers)
    assert listed2.status_code == 200
    body = listed2.json()
    assert body["total"] >= 2
    events = {item["event"] for item in body["items"]}
    assert "enrollment.created" in events
    assert any(e.startswith("recognition.") for e in events)
    dry_run_items = [i for i in body["items"] if i.get("dry_run")]
    assert len(dry_run_items) >= 1

    created = next(item for item in body["items"] if item["event"] == "enrollment.created")
    eid = created["entity_id"]
    filtered = client.get(f"/v1/admin/logs?entity_id={eid}", headers=auth_headers)
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1
    assert all(item["entity_id"] == eid for item in filtered.json()["items"])
