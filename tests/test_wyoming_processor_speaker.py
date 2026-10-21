"""Speaker matching always runs for Wyoming identify (even on gate reject)."""

import uuid

from tests.helpers import wav_bytes


def test_process_utterance_runs_speaker_on_gate_reject(client, auth_headers):
    from openrecognition.integrator.wyoming.processor import process_utterance
    from openrecognition.inference.audio_gate import load_wav_pcm

    label = f"wyoming_gate_{uuid.uuid4().hex[:8]}"
    clip = wav_bytes(duration=0.8, freq=401.0 + (uuid.uuid4().int % 500))
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

    audio, sr = load_wav_pcm(clip)
    import numpy as np

    pcm = (audio * 32767).astype(np.int16).tobytes()
    result = process_utterance(state, pcm, sr, min_confidence=0.5)

    assert result.speaker_match_attempted
    assert result.gallery_count >= 1
    assert result.comparable_speaker_count >= 1
    if result.gate != "accept":
        assert result.reason in (
            "background_noise",
            "silence",
            "music",
            "too_short",
        )
        assert result.candidates is not None
