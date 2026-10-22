from io import BytesIO

from PIL import Image

from tests.helpers import wav_bytes


def _png_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(80, 120, 200))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_enrollment_flow(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "testuser"},
        files=[("files", ("a.wav", wav_bytes(), "audio/wav"))],
    )
    assert r.status_code == 200
    en = r.json()
    assert en["label"] == "testuser"
    eid = en["id"]

    r2 = client.post(
        "/v1/recognize/audio?mode=identify",
        headers=auth_headers,
        files={"file": ("test.wav", wav_bytes(), "audio/wav")},
    )
    assert r2.status_code == 200

    r3 = client.get("/v1/enrollments", headers=auth_headers)
    listed = r3.json()
    row = next(e for e in listed if e["id"] == eid)
    assert row["quality"] is not None
    assert "last_seen_at" in row

    r4 = client.post(f"/v1/enrollments/{eid}/evaluate", headers=auth_headers)
    assert r4.status_code == 200


def test_voice_quality_asks_for_more_phrases_under_eight(client, auth_headers):
    files = [("files", (f"p{i}.wav", wav_bytes(freq=440), "audio/wav")) for i in range(3)]
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "voicefew"},
        files=files,
    )
    assert r.status_code == 200
    eid = r.json()["id"]
    ev = client.post(f"/v1/enrollments/{eid}/evaluate", headers=auth_headers)
    assert ev.status_code == 200
    audio = next(m for m in ev.json()["modalities"] if m["modality"] == "audio")
    assert audio["sample_count"] == 3
    assert "recommend_more_voice_samples" in audio["issues"]
    assert audio["score"] < 0.5


def test_voice_quality_reaches_high_score_with_eight_samples(client, auth_headers):
    files = [("files", (f"p{i}.wav", wav_bytes(freq=440), "audio/wav")) for i in range(8)]
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "voicefull"},
        files=files,
    )
    assert r.status_code == 200
    eid = r.json()["id"]
    ev = client.post(f"/v1/enrollments/{eid}/evaluate", headers=auth_headers)
    assert ev.status_code == 200
    audio = next(m for m in ev.json()["modalities"] if m["modality"] == "audio")
    assert audio["sample_count"] == 8
    assert audio["score"] >= 0.85
    assert "recommend_more_voice_samples" not in audio["issues"]


def test_evaluate_returns_per_modality_quality(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "luke"},
        files=[
            ("files", ("a.wav", wav_bytes(), "audio/wav")),
            ("files", ("face.png", _png_bytes(), "image/png")),
        ],
    )
    assert r.status_code == 200
    eid = r.json()["id"]
    ev = client.post(f"/v1/enrollments/{eid}/evaluate", headers=auth_headers)
    assert ev.status_code == 200
    body = ev.json()
    assert "modalities" in body
    mods = {m["modality"]: m for m in body["modalities"]}
    assert mods["audio"]["sample_count"] >= 1
    assert mods["image"]["sample_count"] >= 1
    assert mods["audio"]["label"] == "Voice"
    assert mods["image"]["label"] == "Face"


def test_person_enrollment_accepts_face_image(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "faceuser"},
        files=[("files", ("face.png", _png_bytes(), "image/png"))],
    )
    assert r.status_code == 200
    assert r.json()["sample_count"] == 1

    r2 = client.post(
        "/v1/recognize/image",
        headers=auth_headers,
        files={"file": ("face.png", _png_bytes(), "image/png")},
    )
    assert r2.status_code == 200


def test_enrollment_rejects_undecodable_webm_without_ffmpeg(client, auth_headers):
    # Minimal WebM/EBML header — not decodable without ffmpeg.
    webm_stub = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "webmuser"},
        files=[("files", ("clip.webm", webm_stub, "audio/webm"))],
    )
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "INVALID_MEDIA"
    assert "ffmpeg" in body["message"].lower() or "decode" in body["message"].lower()


def test_pet_rejects_audio(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "pet", "label": "Pepper"},
        files=[("files", ("bark.wav", wav_bytes(), "audio/wav"))],
    )
    assert r.status_code == 400
    assert "image" in r.json()["message"].lower()


def test_capabilities(client, auth_headers):
    r = client.get("/v1/capabilities", headers=auth_headers)
    assert r.status_code == 200
    assert "recognition_types" in r.json()


def test_api_keys(client, auth_headers):
    r = client.post(
        "/v1/auth/keys",
        headers=auth_headers,
        json={"name": "ha-test", "scopes": ["recognize"]},
    )
    assert r.status_code == 200
    assert "key" in r.json()
    kid = r.json()["id"]

    listed = client.get("/v1/auth/keys", headers=auth_headers)
    assert listed.status_code == 200
    assert any(k["id"] == kid for k in listed.json())

    revoked = client.delete(f"/v1/auth/keys/{kid}", headers=auth_headers)
    assert revoked.status_code == 204

    listed2 = client.get("/v1/auth/keys", headers=auth_headers)
    assert not any(k["id"] == kid for k in listed2.json())


def test_enrollment_threshold_patch_can_be_cleared(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "strict", "threshold": "0.9"},
    )
    assert r.status_code == 200
    eid = r.json()["id"]
    assert r.json()["threshold"] == 0.9

    cleared = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"threshold": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["threshold"] is None

    kept = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert kept.status_code == 200
    assert kept.json()["threshold"] is None
    assert kept.json()["enabled"] is False

    again = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"threshold": 0.92, "enabled": True},
    )
    assert again.status_code == 200
    assert again.json()["threshold"] == 0.92

    omitted = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"label": "strict-renamed"},
    )
    assert omitted.status_code == 200
    assert omitted.json()["threshold"] == 0.92
    assert omitted.json()["label"] == "strict-renamed"

    invalid = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"threshold": 1.5},
    )
    assert invalid.status_code == 422


def test_enrollment_wyoming_min_confidence_patch(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "noisy-mic"},
    )
    assert r.status_code == 200
    eid = r.json()["id"]
    assert r.json()["wyoming_min_confidence"] is None

    set_custom = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"wyoming_min_confidence": 0.55},
    )
    assert set_custom.status_code == 200
    assert set_custom.json()["wyoming_min_confidence"] == 0.55

    kept = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert kept.status_code == 200
    assert kept.json()["wyoming_min_confidence"] == 0.55

    cleared = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"wyoming_min_confidence": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["wyoming_min_confidence"] is None


def test_enrollment_external_ids_patch(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "hauser"},
    )
    assert r.status_code == 200
    eid = r.json()["id"]
    assert r.json().get("external_ids") == {}

    r2 = client.patch(
        f"/v1/enrollments/{eid}",
        headers=auth_headers,
        json={"external_ids": {"homeassistant": "person.hauser"}},
    )
    assert r2.status_code == 200
    assert r2.json()["external_ids"]["homeassistant"] == "person.hauser"

    r3 = client.get(f"/v1/enrollments/{eid}", headers=auth_headers)
    assert r3.json()["external_ids"]["homeassistant"] == "person.hauser"
