"""Admin model download API."""


def test_admin_models_status(client, auth_headers):
    r = client.get("/v1/admin/models", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["hardware"]["effective"] in ("pi", "mini", "desktop", "server")
    assert body["models_dir"]
    assert len(body["catalog"]) >= 7
    keys = {m["key"] for m in body["catalog"]}
    assert "silero_vad" in keys
    assert "speaker_embedding" in keys
    assert "speaker_campplus" in keys
    assert len(body["categories"]) >= 3
    assert len(body["presets"]) >= 3
    voice = next(p for p in body["presets"] if p["id"] == "voice")
    by_key = {m["key"]: m for m in body["catalog"]}
    assert {by_key[key]["category"] for key in voice["keys"]} == {"speech_check", "voice_match"}
    assert all(by_key[key]["suggested"] for key in voice["keys"])
    assert "complete" in voice
    row = next(m for m in body["catalog"] if m["key"] == "face_embedding")
    assert row["category"] == "match_face"
    assert row["label"] == "MobileFace"
    assert row["version"] == "w600k-mbf-v1"
    assert row["onnx"]["embed_dim"] == 512
    assert row["use_for"]
    assert row["contract"]["input_size"] == 112
    speaker = next(m for m in body["catalog"] if m["key"] == "speaker_embedding")
    assert speaker["active"] is True
    assert any(knob["key"] == "max_seconds" for knob in speaker["knobs"])


def test_admin_models_download_skip(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "openrecognition.api.routes.models_admin.download_models",
        lambda pack_dir, keys=None, force=False, extra_specs=None: [
            {
                "key": "silero_vad",
                "status": "skipped",
                "message": "already present (mocked)",
            }
        ],
    )
    r = client.post(
        "/v1/admin/models/download",
        headers=auth_headers,
        json={"keys": ["silero_vad"]},
    )
    assert r.status_code == 200
    assert r.json()["results"][0]["status"] == "skipped"


def test_admin_models_delete_unknown(client, auth_headers):
    r = client.delete("/v1/admin/models/not-a-model", headers=auth_headers)
    assert r.status_code == 404


def test_hardware_override_changes_the_suggestion(client, auth_headers):
    r = client.put(
        "/v1/admin/models/hardware",
        headers=auth_headers,
        json={"tier": "pi"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["hardware"]["override"] == "pi"
    assert body["hardware"]["effective"] == "pi"
    by_key = {row["key"]: row for row in body["catalog"]}
    assert by_key["speaker_campplus"]["suggested"] is True
    assert by_key["speaker_resnet293"]["fit"] == "heavier"
    assert by_key["speaker_resnet293"]["suggested"] is False
    assert by_key["face_edgeface_xs"]["suggested"] is True

    r = client.put(
        "/v1/admin/models/hardware",
        headers=auth_headers,
        json={"tier": "desktop"},
    )
    body = r.json()
    by_key = {row["key"]: row for row in body["catalog"]}
    assert by_key["speaker_resnet293"]["suggested"] is True
    assert by_key["face_auraface"]["suggested"] is True
    assert by_key["speaker_eres2netv2"]["fit"] == "heavier"
    assert by_key["speaker_campplus"]["fit"] == "lighter"

    r = client.put(
        "/v1/admin/models/hardware",
        headers=auth_headers,
        json={"tier": None},
    )
    assert r.status_code == 200
    assert r.json()["hardware"]["override"] is None


def test_model_knobs_round_trip(client, auth_headers):
    r = client.patch(
        "/v1/admin/models/speaker_embedding/settings",
        headers=auth_headers,
        json={"overrides": {"max_seconds": 8}},
    )
    assert r.status_code == 200
    speaker = next(row for row in r.json()["catalog"] if row["key"] == "speaker_embedding")
    knob = next(item for item in speaker["knobs"] if item["key"] == "max_seconds")
    assert knob["value"] == 8
    assert knob["overridden"] is True
    assert speaker["contract"]["embed_dim"] == 256
    state = client.app.state.app_state
    assert state.pool.onnx_config("speaker_embedding")["max_seconds"] == 8
    assert state.pool.onnx_config("speaker_embedding")["embed_dim"] == 256

    edited = client.patch(
        "/v1/admin/models/speaker_embedding/settings",
        headers=auth_headers,
        json={"overrides": {"embed_dim": 192}},
    )
    assert edited.status_code == 200
    speaker = next(row for row in edited.json()["catalog"] if row["key"] == "speaker_embedding")
    assert speaker["contract"]["embed_dim"] == 256
    assert speaker["onnx"]["embed_dim"] == 192
    assert state.pool.onnx_config("speaker_embedding")["embed_dim"] == 192

    rejected = client.patch(
        "/v1/admin/models/speaker_embedding/settings",
        headers=auth_headers,
        json={"overrides": {"not_a_field": 1}},
    )
    assert rejected.status_code == 400

    reset = client.post(
        "/v1/admin/models/speaker_embedding/settings/reset",
        headers=auth_headers,
    )
    assert reset.status_code == 200
    speaker = next(row for row in reset.json()["catalog"] if row["key"] == "speaker_embedding")
    knob = next(item for item in speaker["knobs"] if item["key"] == "max_seconds")
    assert knob["overridden"] is False
    assert knob["value"] == 15
    assert speaker["onnx"]["embed_dim"] == 256


def test_thread_override_round_trip(client, auth_headers):
    r = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"onnx_intra_op_threads": 2},
    )
    assert r.status_code == 200
    models = client.get("/v1/admin/models", headers=auth_headers)
    assert models.json()["threads"]["value"] == 2
    assert models.json()["threads"]["overridden"] is True

    r = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"onnx_intra_op_threads": None},
    )
    assert r.status_code == 200
    models = client.get("/v1/admin/models", headers=auth_headers)
    assert models.json()["threads"]["overridden"] is False
