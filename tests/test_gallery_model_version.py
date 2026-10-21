"""Gallery sample flags vs runtime embedding model versions."""

from pathlib import Path

import numpy as np

from openrecognition.app_state import AppState
from openrecognition.config import Settings
from openrecognition.gallery.db import Database
from openrecognition.gallery.store import GalleryStore
from openrecognition.models.schemas import EnrollmentType


def test_resolve_embedding_uses_onnx_manifest_version(tmp_path):
    pack_dir = tmp_path / "edge"
    pack_dir.mkdir()
    (pack_dir / "model-pack.yaml").write_text(
        "name: edge\nmodels:\n  face_embedding:\n"
        "    file: face_embedding.onnx\n    version: w600k-mbf-v1\n"
    )
    (pack_dir / "face_embedding.onnx").write_bytes(b"\x00" * 8)

    settings = Settings(
        data_dir=tmp_path / "data",
        model_packs_dir=tmp_path,
        pack="edge",
        inference_backend="onnx",
        auth_required=False,
    )
    state = AppState.create(settings)
    assert state.resolve_embedding_model_version("image", "person") == "w600k-mbf-v1"


def test_outdated_flag_when_sample_version_differs(tmp_path):
    data_dir = tmp_path / "data"
    db = Database(data_dir / "openrecognition.db")
    store = GalleryStore(db, data_dir)
    store.set_version_resolver(lambda mod, etype: "w600k-mbf-v1")

    en = store.create_enrollment(EnrollmentType.person, "test")
    vec = np.zeros(512, dtype=np.float32)
    store.add_embedding(en["id"], "image", vec, "face-heuristic-v2")
    store.add_embedding(en["id"], "image", vec, "w600k-mbf-v1")

    samples = store.list_samples(en["id"])
    by_mv = {s.model_version: s.flags for s in samples}
    assert "outdated_model" in by_mv["face-heuristic-v2"]
    assert "outdated_model" not in by_mv["w600k-mbf-v1"]
