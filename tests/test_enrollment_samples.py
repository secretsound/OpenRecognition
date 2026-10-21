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
