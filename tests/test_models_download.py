"""Model download catalog and helpers."""

from pathlib import Path

from openrecognition.models_download import (
    MODEL_CATALOG,
    catalog_for_pack,
    list_catalog,
    list_categories,
    list_presets,
)


def test_catalog_has_sources():
    by_key = {m.key: m for m in MODEL_CATALOG}
    assert by_key["silero_vad"].source == "github"
    assert "github.com" in by_key["silero_vad"].url
    assert by_key["speaker_embedding"].source == "huggingface"
    assert "huggingface.co" in by_key["speaker_embedding"].url
    assert by_key["silero_vad"].category == "speech_check"
    assert by_key["face_embedding"].category == "match_face"
    assert by_key["speaker_embedding"].version == "wespeaker-resnet34-v1"
    assert by_key["speaker_embedding"].onnx["embed_dim"] == 256
    assert by_key["visual_reid"].onnx["backend"] == "classifier"
    assert by_key["visual_reid"].onnx["embed_dim"] == 1000


def test_list_catalog_includes_category_and_tier():
    row = next(r for r in list_catalog(pack="edge") if r["key"] == "speaker_embedding")
    assert row["category"] == "voice_match"
    assert row["tier"] == "essential"
    assert row["label"] == "WeSpeaker ResNet34"
    assert row["version"] == "wespeaker-resnet34-v1"
    assert row["onnx"]["embed_dim"] == 256
    assert row["hardware"] == "pi"
    assert "Voice enrollments" in row["enables"][0]


def test_list_presets_for_edge():
    presets = list_presets(pack="edge")
    ids = {p["id"] for p in presets}
    assert "voice" in ids
    assert "face" in ids
    assert presets[0]["keys"]


def test_list_catalog_edge_pack():
    rows = list_catalog(pack="edge")
    keys = {r["key"] for r in rows}
    assert "silero_vad" in keys
    assert "speaker_embedding" in keys
    assert "face_detector" in keys
    assert "face_embedding" in keys
    assert "animal_detector" in keys
    assert "visual_reid" in keys
    assert "audio_gate_classifier" in keys


def test_catalog_for_pack():
    edge = catalog_for_pack("edge")
    assert len(edge) >= 2
    assert all("edge" in m.packs for m in edge)
