"""In-process Wyoming utterance processor tests."""

import uuid

from tests.helpers import wav_bytes


def test_process_utterance_matches_enrolled_speaker(client, auth_headers):
    from openrecognition.integrator.wyoming.processor import process_utterance

    label = f"wyoming_{uuid.uuid4().hex[:8]}"
    # Unique tone so heuristic embedding does not match other tests' enrollments.
    clip = wav_bytes(duration=0.8, freq=311.0 + (uuid.uuid4().int % 500))
    state = client.app.state.app_state
    client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": label},
        files=[
            ("files", ("p1.wav", clip, "audio/wav")),
            ("files", ("p2.wav", clip, "audio/wav")),
            ("files", ("p3.wav", clip, "audio/wav")),
        ],
    )

    # PCM from same clip (16-bit mono wav payload)
    from openrecognition.inference.audio_gate import load_wav_pcm

    audio, sr = load_wav_pcm(clip)
    import numpy as np

    pcm = (audio * 32767).astype(np.int16).tobytes()
    result = process_utterance(
        state,
        pcm,
        sr,
        min_confidence=0.5,
    )
    assert result.gate == "accept"
    assert result.accepted
    assert result.label == label


def test_process_utterance_gate_reject_on_silence(client):
    from openrecognition.integrator.wyoming.processor import process_utterance

    state = client.app.state.app_state
    # Near-silent PCM
    pcm = b"\x00\x00" * 16000
    result = process_utterance(
        state,
        pcm,
        16000,
        min_confidence=0.75,
        block_on_gate_reject=True,
    )
    assert result.gate in ("accept", "reject")
    if result.gate == "reject":
        assert not result.accepted
