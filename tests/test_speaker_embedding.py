"""Speaker heuristic embedding and recognition tests."""

from openrecognition.gallery import match
from openrecognition.inference.audio_gate import load_wav_pcm
from openrecognition.inference.speaker import heuristic_speaker_embedding

from tests.helpers import wav_bytes


def _embed_wav(data: bytes):
    audio, sr = load_wav_pcm(data)
    return heuristic_speaker_embedding(audio, sr)


def test_same_clip_has_high_similarity():
    data = wav_bytes()
    e1 = _embed_wav(data)
    e2 = _embed_wav(data)
    assert match.cosine_similarity(e1, e2) > 0.99


def test_different_tones_are_less_similar_than_repeat():
    same = _embed_wav(wav_bytes(freq=440.0))
    again = _embed_wav(wav_bytes(freq=440.0))
    other = _embed_wav(wav_bytes(freq=880.0))
    assert match.cosine_similarity(same, again) > match.cosine_similarity(same, other)


def test_enrolled_voice_matches_repeat_clip(client, auth_headers):
    clip = wav_bytes(duration=0.8)
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "voicetest"},
        files=[
            ("files", ("p1.wav", clip, "audio/wav")),
            ("files", ("p2.wav", clip, "audio/wav")),
            ("files", ("p3.wav", clip, "audio/wav")),
        ],
    )
    assert r.status_code == 200

    r2 = client.post(
        "/v1/recognize/audio?mode=identify&min_confidence=0.5&include_candidates=true",
        headers=auth_headers,
        files={"file": ("query.wav", clip, "audio/wav")},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["entities"], body
    assert body["entities"][0]["label"] == "voicetest"
    assert body["entities"][0]["confidence"] >= 0.5
    candidates = body.get("diagnostics", {}).get("candidates", [])
    assert candidates and candidates[0]["accepted"]
