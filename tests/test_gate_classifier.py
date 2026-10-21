"""Optional YAMNet gate classifier tests."""

from pathlib import Path

import numpy as np
import pytest

from openrecognition.inference.gate_classifier import (
    _bucket_scores,
    classify_yamnet,
    gate_with_yamnet,
    refine_gate_with_classifier,
)
from openrecognition.models.schemas import GateResponse

YAMNET = Path("/tmp/yamnet.onnx")


def test_bucket_scores_speech_dominant():
    frame = np.zeros(521, dtype=np.float32)
    frame[0] = 0.9
    frame[132] = 0.05
    frame[507] = 0.05
    scores = _bucket_scores(frame)
    assert scores["speech"] > 0.7
    assert scores["music"] < 0.2


def test_bucket_scores_music_dominant():
    frame = np.zeros(521, dtype=np.float32)
    frame[132] = 0.85
    frame[0] = 0.1
    scores = _bucket_scores(frame)
    assert scores["music"] > 0.5


def test_refine_reject_reason_music():
    gate = GateResponse(
        gate="reject",
        reason="background_noise",
        scores={"speech": 0.1, "music": 0.1, "noise": 0.8},
        latency_ms=5.0,
    )

    class FakeSession:
        def get_inputs(self):
            class Inp:
                name = "waveform"

            return [Inp()]

    def fake_classify(_session, audio, sr):
        return {"speech": 0.1, "music": 0.7, "noise": 0.2}

    import openrecognition.inference.gate_classifier as gc

    original = gc.classify_yamnet
    gc.classify_yamnet = fake_classify
    try:
        out = refine_gate_with_classifier(FakeSession(), np.zeros(8000), 16000, gate)
    finally:
        gc.classify_yamnet = original

    assert out.gate == "reject"
    assert out.reason == "music"
    assert out.scores["music"] > 0.3


def test_refine_accepts_when_merged_speech_high():
    gate = GateResponse(
        gate="reject",
        reason="background_noise",
        scores={"speech": 0.15, "music": 0.05, "noise": 0.8},
        latency_ms=5.0,
    )

    class FakeSession:
        def get_inputs(self):
            class Inp:
                name = "waveform"

            return [Inp()]

    def fake_classify(_session, audio, sr):
        return {"speech": 0.92, "music": 0.04, "noise": 0.04}

    import openrecognition.inference.gate_classifier as gc

    original = gc.classify_yamnet
    gc.classify_yamnet = fake_classify
    try:
        audio = np.full(8000, 0.05, dtype=np.float32)
        out = refine_gate_with_classifier(FakeSession(), audio, 16000, gate)
    finally:
        gc.classify_yamnet = original

    assert out.gate == "accept"
    assert out.reason is None
    assert out.scores["speech"] >= 0.35


@pytest.mark.skipif(not YAMNET.exists(), reason="Download yamnet to /tmp/yamnet.onnx")
def test_yamnet_onnx_runs():
    import onnxruntime as ort

    session = ort.InferenceSession(str(YAMNET), providers=["CPUExecutionProvider"])
    audio = 0.2 * np.sin(np.linspace(0, 40 * np.pi, 16000)).astype(np.float32)
    scores = classify_yamnet(session, audio, 16000)
    assert set(scores) == {"speech", "music", "noise"}
    assert abs(sum(scores.values()) - 1.0) < 0.01

    gate = gate_with_yamnet(session, audio, 16000)
    assert gate.gate in ("accept", "reject")
    assert gate.latency_ms >= 0
