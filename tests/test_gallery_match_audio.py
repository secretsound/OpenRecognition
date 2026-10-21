"""Gallery matching uses per-modality model version centroids."""

import numpy as np

from openrecognition.gallery.db import Database
from openrecognition.gallery.match import accept_threshold, rank_gallery_matches
from openrecognition.gallery.store import GalleryStore
from openrecognition.inference.inference_policy import InferencePolicy
from openrecognition.inference.session_pool import ModelSessionPool
from openrecognition.inference.speaker import EMBED_DIM, SpeakerEngine
from openrecognition.inference.vision import VisionEngine
from openrecognition.models.schemas import EnrollmentType


def _engines(tmp_path):
    pool = ModelSessionPool(tmp_path / "pack")
    policy = InferencePolicy(pool, "heuristic")
    return SpeakerEngine(pool, policy), VisionEngine(pool, policy)


def _axis(dim: int, index: int = 0, value: float = 1.0) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    vec[index] = value
    return vec


def test_get_embeddings_for_match_audio_model_version(tmp_path):
    data_dir = tmp_path / "data"
    db = Database(data_dir / "openrecognition.db")
    store = GalleryStore(db, data_dir)

    en = store.create_enrollment(EnrollmentType.person, "Luke")
    face = np.random.randn(512).astype(np.float32)
    face /= np.linalg.norm(face)
    voice = np.random.randn(256).astype(np.float32)
    voice /= np.linalg.norm(voice)

    store.add_embedding(en["id"], "image", face, "w600k-mbf-v1")
    store.add_embedding(en["id"], "audio", voice, "wespeaker-resnet34-v1")

    all_items = store.get_embeddings_for_match()
    assert len(all_items) == 2
    assert sorted(item["vector"].size for item in all_items) == [256, 512]
    image_items = store.get_embeddings_for_match(
        modality="image",
        model_version="w600k-mbf-v1",
    )
    assert len(image_items) == 1
    assert image_items[0]["vector"].size == 512

    audio_items = store.get_embeddings_for_match(
        modality="audio",
        model_version="wespeaker-resnet34-v1",
    )
    assert len(audio_items) == 1
    assert audio_items[0]["vector"].size == 256
    assert audio_items[0]["label"] == "Luke"

    missing = store.get_embeddings_for_match(
        modality="audio",
        model_version="other-speaker-v9",
    )
    assert missing == []


def test_face_only_person_not_in_audio_gallery(tmp_path):
    data_dir = tmp_path / "data"
    db = Database(data_dir / "openrecognition.db")
    store = GalleryStore(db, data_dir)

    en = store.create_enrollment(EnrollmentType.person, "FaceOnly")
    face = np.zeros(512, dtype=np.float32)
    store.add_embedding(en["id"], "image", face, "w600k-mbf-v1")

    audio_items = store.get_embeddings_for_match(
        modality="audio",
        model_version="wespeaker-resnet34-v1",
    )
    assert audio_items == []


def test_face_and_voice_both_match(tmp_path):
    data_dir = tmp_path / "data"
    db = Database(data_dir / "openrecognition.db")
    store = GalleryStore(db, data_dir)
    speaker, vision = _engines(tmp_path)
    face_ver = vision.current_face_model_version()
    voice_ver = speaker.current_model_version()

    face = _axis(512)
    voice = _axis(EMBED_DIM)
    en = store.create_enrollment(EnrollmentType.person, "Luke")
    store.add_embedding(en["id"], "image", face, face_ver)
    store.add_embedding(en["id"], "audio", voice, voice_ver)

    stored = db.fetchone("SELECT centroid FROM enrollments WHERE id = ?", (en["id"],))
    assert len(stored["centroid"]) // 4 == voice.size

    image_gallery = store.image_embeddings_for_match(
        face_ver, vision.current_visual_model_version()
    )
    audio_gallery = store.get_embeddings_for_match(
        modality="audio", model_version=voice_ver
    )
    face_hits = vision.match_gallery(face, image_gallery, {"person"}, 0.5, False, "face")
    voice_hits = speaker.match_gallery(voice, audio_gallery, 0.5, False)
    assert face_hits[0]["label"] == "Luke"
    assert voice_hits[0]["label"] == "Luke"
    assert face_hits[0]["modality"] == "image"
    assert voice_hits[0]["modality"] == "audio"


def test_enrollment_threshold_raises_the_bar(tmp_path):
    assert accept_threshold({"threshold": 0.95}, 0.5) == 0.95
    assert accept_threshold({"threshold": 0.2}, 0.5) == 0.5
    assert accept_threshold({"threshold": None}, 0.5) == 0.5

    data_dir = tmp_path / "data"
    db = Database(data_dir / "openrecognition.db")
    store = GalleryStore(db, data_dir)
    speaker, _vision = _engines(tmp_path)
    version = speaker.current_model_version()
    enrolled = _axis(EMBED_DIM)
    # cosine similarity with enrolled is 0.7
    query = _axis(EMBED_DIM, 0, 0.7)
    query[1] = np.float32(np.sqrt(1.0 - 0.49))

    strict = store.create_enrollment(EnrollmentType.person, "Strict", threshold=0.95)
    store.add_embedding(strict["id"], "audio", enrolled, version)
    gallery = store.get_embeddings_for_match(modality="audio", model_version=version)
    ranked = rank_gallery_matches(query, gallery, {"person"}, 0.5, "speaker", "audio")
    assert ranked[0]["accepted"] is False
    assert ranked[0]["threshold_used"] == 0.95
    assert speaker.match_gallery(query, gallery, 0.5, False) == []

    exact = speaker.match_gallery(enrolled, gallery, 0.5, False)
    assert exact[0]["label"] == "Strict"
    assert exact[0]["threshold_used"] == 0.95

    loose = store.create_enrollment(EnrollmentType.person, "Loose", threshold=0.5)
    store.add_embedding(loose["id"], "audio", enrolled, version)
    both = store.get_embeddings_for_match(modality="audio", model_version=version)
    hits = speaker.match_gallery(query, both, 0.5, False)
    assert [h["label"] for h in hits] == ["Loose"]
    assert hits[0]["threshold_used"] == 0.5
