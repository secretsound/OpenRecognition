"""Model download catalog and helpers."""

from openrecognition.models_download import (
    MODEL_CATALOG,
    catalog_for_pack,
    list_catalog,
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
    assert by_key["speaker_campplus"].onnx["embed_dim"] == 512
    assert by_key["speaker_campplus"].hardware == "pi"
    assert by_key["speaker_resnet293"].hardware == "desktop"
    assert by_key["visual_reid"].onnx["backend"] == "classifier"
    assert by_key["visual_reid"].onnx["embed_dim"] == 1000


def test_list_catalog_includes_category_and_tier():
    row = next(r for r in list_catalog() if r["key"] == "speaker_embedding")
    assert row["category"] == "voice_match"
    assert row["tier"] == "essential"
    assert row["label"] == "WeSpeaker ResNet34"
    assert row["version"] == "wespeaker-resnet34-v1"
    assert row["onnx"]["embed_dim"] == 256
    assert row["hardware"] == "mini"
    assert "Voice enrollments" in row["enables"][0]


def test_list_presets_cover_categories():
    presets = list_presets()
    ids = {p["id"] for p in presets}
    assert "voice" in ids
    assert "face" in ids
    voice = next(p for p in presets if p["id"] == "voice")
    assert "silero_vad" in voice["keys"]
    assert "speaker_embedding" in voice["keys"]


def test_list_catalog_has_the_builtin_set():
    rows = list_catalog()
    keys = {r["key"] for r in rows}
    assert "silero_vad" in keys
    assert "speaker_embedding" in keys
    assert "speaker_campplus" in keys
    assert "face_detector" in keys
    face = next(r for r in rows if r["key"] == "face_detector")
    pet = next(r for r in rows if r["key"] == "animal_detector")
    assert face["enables"] == ["Accurate face crops before embedding"]
    assert pet["enables"] == ["Pet/object region crops (not full-frame guess)"]
    assert "face_embedding" in keys
    assert "face_w600k_r50" in keys
    assert "animal_detector" in keys
    assert "visual_reid" in keys
    assert "audio_gate_classifier" in keys


def test_every_model_has_planning_facts():
    from openrecognition.models_download import MODEL_GUIDE, public_page

    missing = [spec.key for spec in MODEL_CATALOG if spec.key not in MODEL_GUIDE]
    assert missing == []
    for spec in MODEL_CATALOG:
        guide = MODEL_GUIDE[spec.key]
        assert guide.page_url.startswith("https://")
        assert not guide.page_url.lower().endswith(".onnx")
        assert guide.disk_bytes > 1000
        assert guide.memory_mb >= 32
        assert len(guide.summary) > 40
    assert public_page(
        "https://huggingface.co/fal/AuraFace-v1/resolve/main/glintr100.onnx"
    ) == "https://huggingface.co/fal/AuraFace-v1"
    assert public_page("https://example.com/weights/model.onnx") == ""


def test_catalog_for_pack_still_lists_shared_models():
    edge = catalog_for_pack("edge")
    assert len(edge) >= 2
    assert all("edge" in m.packs for m in edge)
