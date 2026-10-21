"""Vision ONNX (optional downloaded weights)."""

from pathlib import Path

import numpy as np
import pytest

from openrecognition.inference.inference_policy import InferencePolicy
from openrecognition.inference.session_pool import ModelSessionPool
from openrecognition.inference.vision import VisionEngine, _image_to_array

PACK_DIR = Path(__file__).resolve().parents[1] / "model-packs" / "edge"
FACE_DET = PACK_DIR / "face_detector.onnx"
FACE_EMB = PACK_DIR / "face_embedding.onnx"
VIS_REID = PACK_DIR / "visual_reid.onnx"


@pytest.mark.skipif(
    not (FACE_DET.exists() and FACE_EMB.exists()),
    reason="Run: openrecognition models download --only face_detector,face_embedding",
)
def test_face_onnx_embed_dim():
    pool = ModelSessionPool(PACK_DIR)
    policy = InferencePolicy(pool, "onnx")
    engine = VisionEngine(pool, policy)
    pixels = np.random.rand(320, 240, 3).astype(np.float32)
    emb = engine.embed_face(_pixels_to_png(pixels))
    assert emb.shape == (512,)
    assert abs(float(np.linalg.norm(emb)) - 1.0) < 1e-4


@pytest.mark.skipif(
    not VIS_REID.exists(),
    reason="Run: openrecognition models download --only visual_reid",
)
def test_visual_reid_onnx_embed_dim():
    pool = ModelSessionPool(PACK_DIR)
    policy = InferencePolicy(pool, "onnx")
    engine = VisionEngine(pool, policy)
    pixels = np.random.rand(224, 224, 3).astype(np.float32)
    emb = engine.embed_visual(_pixels_to_png(pixels))
    assert emb.shape == (1000,)
    assert abs(float(np.linalg.norm(emb)) - 1.0) < 1e-4


def _pixels_to_png(pixels: np.ndarray) -> bytes:
    from io import BytesIO

    from PIL import Image

    img = Image.fromarray((pixels * 255).astype(np.uint8))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_image_to_array_preserves_small_resolution():
    data = _pixels_to_png(np.zeros((64, 64, 3), dtype=np.float32))
    arr = _image_to_array(data)
    assert arr.shape[:2] == (64, 64)
