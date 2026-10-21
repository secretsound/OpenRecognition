"""Inference backend selection (ONNX vs heuristic)."""

from pathlib import Path

import pytest

from openrecognition.inference.inference_policy import InferencePolicy
from openrecognition.inference.session_pool import ModelSessionPool

EDGE_PACK = Path(__file__).resolve().parents[1] / "model-packs" / "edge"
HAS_SILERO = (EDGE_PACK / "silero_vad.onnx").exists()


def test_heuristic_mode_ignores_onnx_files():
    if not HAS_SILERO:
        pytest.skip("silero_vad.onnx not downloaded")
    pool = ModelSessionPool(EDGE_PACK)
    policy = InferencePolicy(pool, "heuristic")
    assert policy.should_use_onnx("silero_vad") is False
    assert policy.get_session("silero_vad") is None
    assert policy.effective_backend("silero_vad") == "heuristic"


def test_auto_mode_uses_onnx_when_present():
    if not HAS_SILERO:
        pytest.skip("silero_vad.onnx not downloaded")
    pool = ModelSessionPool(EDGE_PACK)
    policy = InferencePolicy(pool, "auto")
    assert policy.should_use_onnx("silero_vad") is True
    assert policy.get_session("silero_vad") is not None


def test_onnx_mode_warns_when_file_missing(tmp_path):
    pack_dir = tmp_path / "edge"
    pack_dir.mkdir()
    (pack_dir / "model-pack.yaml").write_text("name: edge\nmodels: {}\n")
    pool = ModelSessionPool(pack_dir)
    policy = InferencePolicy(pool, "onnx")
    assert policy.should_use_onnx("silero_vad") is False
    warn = policy.fallback_warning("silero_vad")
    assert warn is not None
    assert "missing" in warn.lower()
    assert policy.identity_blocked("speaker_embedding")


def test_auto_mode_warns_when_identity_model_missing(tmp_path):
    pack_dir = tmp_path / "edge"
    pack_dir.mkdir()
    (pack_dir / "model-pack.yaml").write_text("name: edge\nmodels: {}\n")
    pool = ModelSessionPool(pack_dir)
    policy = InferencePolicy(pool, "auto")
    warn = policy.fallback_warning("speaker_embedding")
    assert warn is not None
    assert "heuristic fallback" in warn
    assert policy.fallback_warning("silero_vad") is None
    assert policy.identity_blocked("speaker_embedding") is None


def test_admin_patch_inference_backend(client, auth_headers):
    r = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"inference_backend": "heuristic"},
    )
    assert r.status_code == 200
    assert r.json()["inference_backend"] == "heuristic"
    assert r.json()["inference_status"]["requested"] == "heuristic"

    r2 = client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"inference_backend": "auto"},
    )
    assert r2.status_code == 200
    assert r2.json()["inference_backend"] == "auto"

    # Leave persisted runtime on heuristic so module-scoped app state stays CI-stable.
    client.patch(
        "/v1/admin/settings",
        headers=auth_headers,
        json={"inference_backend": "heuristic"},
    )


def test_health_includes_inference(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "inference" in body
    assert body["inference"]["requested"] in ("auto", "onnx", "heuristic")
