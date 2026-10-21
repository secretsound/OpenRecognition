import sqlite3

import numpy as np
import pytest

from openrecognition.gallery.db import Database
from openrecognition.gallery.store import GalleryStore
from openrecognition.models.schemas import EnrollmentType


def test_foreign_keys_and_wal(tmp_path):
    db = Database(tmp_path / "openrecognition.db")
    mode = db.fetchone("PRAGMA journal_mode")
    assert mode[0].lower() == "wal"
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO embeddings
               (id, enrollment_id, modality, model_version, vector, dim, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("emb", "missing-enrollment", "audio", "v", b"\x00\x00", 1, "now"),
        )


def test_delete_enrollment_removes_children(tmp_path):
    data = tmp_path / "data"
    db = Database(data / "openrecognition.db")
    store = GalleryStore(db, data)
    en = store.create_enrollment(EnrollmentType.person, "Ada")
    store.add_embedding(en["id"], "audio", np.zeros(4, dtype=np.float32), "v")
    db.execute(
        """INSERT INTO presence
           (enrollment_id, label, type, last_seen_at, last_modality)
           VALUES (?, ?, ?, ?, ?)""",
        (en["id"], "Ada", "person", "now", "audio"),
    )
    assert store.delete_enrollment(en["id"]) is True
    assert db.fetchone("SELECT id FROM enrollments WHERE id = ?", (en["id"],)) is None
    assert db.fetchone("SELECT id FROM embeddings WHERE enrollment_id = ?", (en["id"],)) is None
    assert (
        db.fetchone("SELECT enrollment_id FROM presence WHERE enrollment_id = ?", (en["id"],))
        is None
    )
