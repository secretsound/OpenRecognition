"""Hardware suggestion picks the heaviest model a machine can run."""

import numpy as np

from openrecognition.hardware import detect_hardware

from openrecognition.gallery.db import Database
from openrecognition.gallery.model_registry import (
    enrollment_count,
    fit_for,
    list_records,
    reenroll_count,
    removal_block_reason,
    suggested_key,
    sync_catalog,
    update_knobs,
)
from openrecognition.gallery.store import GalleryStore
from openrecognition.models.schemas import EnrollmentType


def test_suggestion_follows_the_machine(tmp_path):
    db = Database(tmp_path / "app.db")
    sync_catalog(db)
    records = list_records(db)
    assert suggested_key(records, "voice_match", "pi") == "speaker_campplus"
    assert suggested_key(records, "voice_match", "mini") == "speaker_embedding"
    assert suggested_key(records, "voice_match", "desktop") == "speaker_resnet293"
    assert suggested_key(records, "voice_match", "server") == "speaker_eres2netv2"
    assert suggested_key(records, "match_face", "pi") == "face_edgeface_xs"
    assert suggested_key(records, "match_face", "mini") == "face_adaface_ir50"
    assert suggested_key(records, "match_face", "desktop") == "face_auraface"
    assert suggested_key(records, "match_face", "server") == "face_adaface_ir101"
    assert suggested_key(records, "find_face", "pi") == "face_yunet"
    assert suggested_key(records, "find_face", "desktop") == "face_scrfd_10g"
    assert suggested_key(records, "find_pet", "server") == "animal_yolo11l"
    assert suggested_key(records, "match_pet", "pi") == "visual_reid"
    assert suggested_key(records, "match_pet", "mini") == "visual_dinov2_s"
    assert suggested_key(records, "speech_check", "pi") == "silero_vad"
    assert suggested_key(records, "speech_check", "mini") == "silero_vad_v6"
    assert fit_for("pi", "desktop") == "lighter"
    assert fit_for("desktop", "pi") == "heavier"
    assert fit_for("server", "desktop") == "heavier"
    assert fit_for("desktop", "server") == "lighter"


def test_server_tier_follows_memory_and_cores(monkeypatch):
    monkeypatch.setattr("openrecognition.hardware.platform.machine", lambda: "x86_64")

    monkeypatch.setattr("openrecognition.hardware._memory_mb", lambda: 64 * 1024)
    monkeypatch.setattr("openrecognition.hardware.os.cpu_count", lambda: 8)
    assert detect_hardware()["tier"] == "server"

    monkeypatch.setattr("openrecognition.hardware._memory_mb", lambda: 24 * 1024)
    monkeypatch.setattr("openrecognition.hardware.os.cpu_count", lambda: 16)
    assert detect_hardware()["tier"] == "server"

    monkeypatch.setattr("openrecognition.hardware._memory_mb", lambda: 20 * 1024)
    monkeypatch.setattr("openrecognition.hardware.os.cpu_count", lambda: 8)
    assert detect_hardware()["tier"] == "desktop"

    monkeypatch.setattr("openrecognition.hardware._memory_mb", lambda: 12 * 1024)
    assert detect_hardware()["tier"] == "mini"


def test_yunet_decode_one_cell():
    from openrecognition.inference.yunet import decode_yunet_level

    boxes = decode_yunet_level(
        np.array([1.0], dtype=np.float32),
        np.array([1.0], dtype=np.float32),
        np.array([[0, 0, np.log(2), np.log(2)]], dtype=np.float32),
        stride=8,
        cols=1,
        conf_thres=0.5,
    )
    assert len(boxes) == 1
    x1, y1, x2, y2, score = boxes[0]
    assert score == 1.0
    assert (x1, y1, x2, y2) == (-8.0, -8.0, 8.0, 8.0)


def test_knobs_and_onnx_fields_can_be_overridden(tmp_path):
    db = Database(tmp_path / "app.db")
    sync_catalog(db)
    updated = update_knobs(db, "speaker_embedding", {"max_seconds": 8, "embed_dim": 192})
    assert updated.effective["max_seconds"] == 8
    assert updated.effective["embed_dim"] == 192
    assert updated.contract["embed_dim"] == 256
    try:
        update_knobs(db, "speaker_embedding", {"not_a_field": 1})
    except ValueError as exc:
        assert "not a setting" in str(exc)
    else:
        raise AssertionError("unknown fields should be rejected")


def test_reenroll_count_counts_other_versions(tmp_path):
    db = Database(tmp_path / "app.db")
    store = GalleryStore(db, tmp_path)
    enrollment = store.create_enrollment(EnrollmentType.person, "ada")
    vector = np.zeros(512, dtype=np.float32)
    store.add_embedding(enrollment["id"], "image", vector, "old-face")
    assert reenroll_count(db, "match_face", "w600k-mbf-v1") == 1
    assert reenroll_count(db, "speech_check", "anything") == 0
    assert enrollment_count(db, "match_face", "old-face") == 1
    assert enrollment_count(db, "match_face", "w600k-mbf-v1") == 0


def test_model_file_stays_while_enrollments_use_it(tmp_path):
    db = Database(tmp_path / "app.db")
    sync_catalog(db)
    store = GalleryStore(db, tmp_path)
    enrollment = store.create_enrollment(EnrollmentType.person, "ada")
    store.add_embedding(
        enrollment["id"], "image", np.zeros(512, dtype=np.float32), "w600k-mbf-v1"
    )
    assert enrollment_count(db, "match_face", "w600k-mbf-v1") == 1
    reason = removal_block_reason(db, "face_embedding")
    assert reason is not None and "still use" in reason
    assert removal_block_reason(db, "face_w600k_r50") is None
