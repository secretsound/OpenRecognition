from tests.helpers import wav_bytes


def test_audio_gate(client, auth_headers):
    r = client.post(
        "/v1/audio/gate",
        headers=auth_headers,
        files={"file": ("test.wav", wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["gate"] in ("accept", "reject")
    assert "scores" in data


def test_recognize_audio_gate_mode(client, auth_headers):
    r = client.post(
        "/v1/recognize/audio?mode=gate",
        headers=auth_headers,
        files={"file": ("test.wav", wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 200
    assert "gate" in r.json()
