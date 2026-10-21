"""WeSpeaker speaker ONNX (optional downloaded weights)."""

from pathlib import Path

import numpy as np
import pytest

from openrecognition.gallery import match
from openrecognition.inference.audio_gate import load_wav_pcm
from openrecognition.inference.inference_policy import InferencePolicy
from openrecognition.inference.session_pool import ModelSessionPool
from openrecognition.inference.speaker import SpeakerEngine
from tests.helpers import wav_bytes

EDGE_PACK = Path(__file__).resolve().parents[1] / "model-packs" / "edge"
SPEAKER_ONNX = EDGE_PACK / "speaker_embedding.onnx"


@pytest.mark.skipif(not SPEAKER_ONNX.exists(), reason="Run: python tools/download_models.py --only speaker_embedding")
def test_wespeaker_embed_repeatable():
    pool = ModelSessionPool(EDGE_PACK)
    policy = InferencePolicy(pool, "onnx")
    engine = SpeakerEngine(pool, policy)
    data = wav_bytes(duration=1.0)
    e1 = engine.embed(data)
    e2 = engine.embed(data)
    assert engine.model_version == "wespeaker-resnet34-v1"
    assert e1.shape == (256,)
    assert match.cosine_similarity(e1, e2) > 0.99


def test_wespeaker_same_clip_high_similarity():
    if not SPEAKER_ONNX.exists():
        pytest.skip("speaker_embedding.onnx not present")
    pool = ModelSessionPool(EDGE_PACK)
    policy = InferencePolicy(pool, "onnx")
    engine = SpeakerEngine(pool, policy)
    clip = wav_bytes(duration=1.0)
    e1 = engine.embed(clip)
    e2 = engine.embed(clip)
    assert match.cosine_similarity(e1, e2) > 0.95
