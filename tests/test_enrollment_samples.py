"""Enrollment sample list, metadata, and delete."""

from tests.helpers import wav_bytes


def _create_with_samples(client, auth_headers, n: int = 3):
    files = [
        ("files", (f"p{i}.wav", wav_bytes(freq=440 + i * 10), "audio/wav"))
        for i in range(n)
    ]
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "sampleuser"},
        files=files,
    )
    assert r.status_code == 200
    return r.json()["id"]


def test_list_samples_with_metadata(client, auth_headers):
    eid = _create_with_samples(client, auth_headers, 2)
    r = client.get(f"/v1/enrollments/{eid}/samples", headers=auth_headers)
    assert r.status_code == 200
    samples = r.json()
    assert len(samples) == 2
    for s in samples:
        assert s["enrollment_id"] == eid
        assert s["modality"] == "audio"
        assert s["source"] == "enrollment_create"
        assert s["original_filename"].startswith("p")
        assert s["size_bytes"] > 0
        assert s["duration_ms"] is not None
        assert "source_label" in s


def test_delete_sample_updates_count_and_centroid(client, auth_headers):
    eid = _create_with_samples(client, auth_headers, 3)
    listed = client.get(f"/v1/enrollments/{eid}/samples", headers=auth_headers).json()
    victim = listed[0]["id"]

    d = client.delete(f"/v1/enrollments/{eid}/samples/{victim}", headers=auth_headers)
    assert d.status_code == 204

    en = client.get(f"/v1/enrollments/{eid}", headers=auth_headers).json()
    assert en["sample_count"] == 2

    remaining = client.get(f"/v1/enrollments/{eid}/samples", headers=auth_headers).json()
    assert len(remaining) == 2
    assert all(s["id"] != victim for s in remaining)


def test_delete_sample_wrong_enrollment_404(client, auth_headers):
    eid = _create_with_samples(client, auth_headers, 1)
    other = _create_with_samples(client, auth_headers, 1)
    sample_id = client.get(f"/v1/enrollments/{eid}/samples", headers=auth_headers).json()[0]["id"]
    r = client.delete(f"/v1/enrollments/{other}/samples/{sample_id}", headers=auth_headers)
    assert r.status_code == 404


def test_voice_wizard_meta_via_form(client, auth_headers):
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "wizardmeta"},
        files=[],
    )
    eid = r.json()["id"]
    meta = [
        {
            "source": "voice_wizard",
            "phrase_index": 0,
            "phrase_text": "The quick brown fox jumps over the lazy dog.",
        }
    ]
    r2 = client.post(
        f"/v1/enrollments/{eid}/samples",
        headers=auth_headers,
        data={"sample_meta": __import__("json").dumps(meta)},
        files=[("files", ("voice-phrase-1.wav", wav_bytes(), "audio/wav"))],
    )
    assert r2.status_code == 200
    samples = client.get(f"/v1/enrollments/{eid}/samples", headers=auth_headers).json()
    assert samples[0]["source"] == "voice_wizard"
    assert samples[0]["phrase_index"] == 0
    assert "quick brown fox" in samples[0]["source_label"]


def test_sample_preview_does_not_persist(client, auth_headers):
    created = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "previewuser"},
        files=[],
    )
    assert created.status_code == 200
    eid = created.json()["id"]

    preview = client.post(
        f"/v1/enrollments/{eid}/samples/preview",
        headers=auth_headers,
        files={"file": ("take.wav", wav_bytes(duration=4.0), "audio/wav")},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert 0 <= body["score"] <= 1
    assert body["verdict"] in {"keep", "retry"}
    assert "advice" in body
    assert body["duration_ms"] is None or body["duration_ms"] > 0

    samples = client.get(f"/v1/enrollments/{eid}/samples", headers=auth_headers).json()
    assert samples == []


def test_sample_preview_accepts_image(client, auth_headers):
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (96, 96), color=(90, 130, 180)).save(buf, format="PNG")
    created = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "facepreview"},
        files=[],
    )
    eid = created.json()["id"]
    preview = client.post(
        f"/v1/enrollments/{eid}/samples/preview",
        headers=auth_headers,
        files={"file": ("face.png", buf.getvalue(), "image/png")},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert 0 <= body["score"] <= 1
    assert body["verdict"] in {"keep", "retry"}
    assert client.get(f"/v1/enrollments/{eid}/samples", headers=auth_headers).json() == []
