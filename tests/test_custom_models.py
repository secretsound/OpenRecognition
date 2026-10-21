"""Admin-added models for an existing category."""

from pathlib import Path

from openrecognition.gallery.custom_models import apply_overrides, create_custom, set_active
from openrecognition.gallery.db import Database
from openrecognition.inference.session_pool import ModelSessionPool


def test_custom_model_can_take_over_a_category(tmp_path: Path):
    db = Database(tmp_path / "app.db")
    spec = create_custom(
        db,
        label="Community voice",
        category="voice_match",
        version="community-v1",
        url="https://example.com/voice.onnx",
        onnx={"embed_dim": 192},
    )
    assert spec.key.startswith("custom_")
    assert spec.onnx["embed_dim"] == 192
    assert spec.onnx["sample_rate"] == 16000
    assert spec.version == "community-v1"

    pool = ModelSessionPool(tmp_path / "models")
    apply_overrides(pool, db)
    assert pool.model_version("speaker_embedding") == "wespeaker-resnet34-v1"

    set_active(db, "voice_match", spec.key)
    apply_overrides(pool, db)
    assert pool.model_version("speaker_embedding") == "community-v1"
    assert pool.onnx_config("speaker_embedding")["embed_dim"] == 192
    assert pool.onnx_path("speaker_embedding") is None


def test_admin_custom_model_round_trip(client, auth_headers):
    created = client.post(
        "/v1/admin/models/custom",
        headers=auth_headers,
        json={
            "label": "Community voice",
            "category": "voice_match",
            "version": "community-v1",
            "url": "https://example.com/voice.onnx",
        },
    )
    assert created.status_code == 200, created.text
    key = created.json()["key"]

    status = client.get("/v1/admin/models", headers=auth_headers)
    assert status.status_code == 200
    rows = {row["key"]: row for row in status.json()["catalog"]}
    assert rows[key]["origin"] == "custom"
    assert rows[key]["category"] == "voice_match"
    assert rows[key]["version"] == "community-v1"
    assert rows[key]["active"] is False
    assert rows["speaker_embedding"]["active"] is True
    assert rows["speaker_embedding"]["version"] == "wespeaker-resnet34-v1"

    bad = client.post(
        "/v1/admin/models/custom",
        headers=auth_headers,
        json={
            "label": "Nope",
            "category": "voice_match",
            "version": "v",
            "url": "ftp://example.com/voice.onnx",
        },
    )
    assert bad.status_code == 400

    activated = client.post(
        "/v1/admin/models/active",
        headers=auth_headers,
        json={"category": "voice_match", "key": key},
    )
    assert activated.status_code == 200
    state = client.app.state.app_state
    assert state.pool.model_version("speaker_embedding") == "community-v1"

    removed = client.delete(f"/v1/admin/models/custom/{key}", headers=auth_headers)
    assert removed.status_code == 200
    status = client.get("/v1/admin/models", headers=auth_headers)
    keys = {row["key"] for row in status.json()["catalog"]}
    assert key not in keys
    assert state.pool.model_version("speaker_embedding") == "wespeaker-resnet34-v1"
