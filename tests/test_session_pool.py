from pathlib import Path

from openrecognition.inference.session_pool import ModelSessionPool

PACK = Path(__file__).resolve().parents[1] / "model-packs" / "edge"


def test_list_models_without_onnx():
    pool = ModelSessionPool(PACK)
    models = pool.list_models()
    if not (PACK / "silero_vad.onnx").exists():
        assert "heuristic" in models
    else:
        assert "silero_vad" in models
