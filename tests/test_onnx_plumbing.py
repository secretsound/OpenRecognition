"""ONNX plumbing tests (optional real Silero weights)."""

from pathlib import Path

import numpy as np
import pytest

from openrecognition.inference.audio_gate import heuristic_gate, resample
from openrecognition.inference.onnx_helpers import l2_normalize
from openrecognition.inference.session_pool import ModelSessionPool
from tests.helpers import wav_bytes

PACK_DIR = Path(__file__).resolve().parents[1] / "model-packs" / "edge"
SILERO = PACK_DIR / "silero_vad.onnx"


def test_l2_normalize():
    v = np.array([3.0, 4.0], dtype=np.float32)
    out = l2_normalize(v)
    assert abs(float(np.linalg.norm(out)) - 1.0) < 1e-5


def test_session_pool_uses_catalog_runtime(tmp_path: Path):
    pool = ModelSessionPool(tmp_path)
    assert pool.model_version("silero_vad") == "silero-vad-v4"
    assert pool.onnx_config("speaker_embedding")["embed_dim"] == 256
    assert pool.onnx_config("visual_reid")["backend"] == "classifier"
    assert pool.onnx_config("visual_reid")["embed_dim"] == 1000
    assert pool.onnx_config("face_embedding")["input_size"] == 112
    assert pool.onnx_path("silero_vad") is None


@pytest.mark.skipif(not SILERO.exists(), reason="Run tools/download_models.py for Silero")
def test_silero_gate_on_wav():
    from openrecognition.inference.audio_gate import load_wav_pcm
    from openrecognition.inference.silero_vad import gate_with_silero

    pool = ModelSessionPool(PACK_DIR)
    session = pool.get_session("silero_vad")
    assert session is not None
    audio, sr = load_wav_pcm(wav_bytes())
    gate = gate_with_silero(session, audio, sr)
    assert gate.gate in ("accept", "reject")
    assert gate.latency_ms >= 0


def test_heuristic_gate_still_works():
    audio = np.zeros(16000, dtype=np.float32)
    audio[4000:12000] = 0.3 * np.sin(np.linspace(0, 40 * np.pi, 8000))
    gate = heuristic_gate(audio, 16000)
    assert gate.gate in ("accept", "reject")
