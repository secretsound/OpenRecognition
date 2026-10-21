"""Admin model download API."""

from pathlib import Path

import pytest

EDGE_PACK = Path(__file__).resolve().parents[1] / "model-packs" / "edge"


def test_admin_models_status(client, auth_headers):
    r = client.get("/v1/admin/models", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["pack"] == "edge"
    assert len(body["catalog"]) >= 7
    keys = {m["key"] for m in body["catalog"]}
    assert "silero_vad" in keys
    assert "speaker_embedding" in keys
    assert len(body["categories"]) >= 3
    assert len(body["presets"]) >= 3
    recs = {item["id"]: item for item in body["recommendations"]}
    assert "edge" in recs
    assert "silero_vad" in recs["edge"]["keys"]
    assert "speaker_embedding" in recs["edge"]["keys"]
    voice = next(p for p in body["presets"] if p["id"] == "voice")
    assert "silero_vad" in voice["keys"]
    assert "complete" in voice
    row = next(m for m in body["catalog"] if m["key"] == "face_embedding")
    assert row["category"] == "match_face"
    assert row["label"] == "MobileFace"
    assert row["version"] == "w600k-mbf-v1"
    assert row["onnx"]["embed_dim"] == 512
    assert row["use_for"]


def test_admin_models_download_skip(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "openrecognition.api.routes.models_admin.download_models",
        lambda pack_dir, keys=None, force=False, extra_specs=None: [
            {
                "key": "silero_vad",
                "status": "skipped",
                "message": "already present (mocked)",
            }
        ],
    )
    r = client.post(
        "/v1/admin/models/download",
        headers=auth_headers,
        json={"keys": ["silero_vad"]},
    )
    assert r.status_code == 200
    assert r.json()["results"][0]["status"] == "skipped"


def test_admin_models_delete_unknown(client, auth_headers):
    r = client.delete("/v1/admin/models/not-a-model", headers=auth_headers)
    assert r.status_code == 404
