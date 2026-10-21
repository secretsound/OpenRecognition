"""Recommendation sets imported from model-pack.yaml."""

from pathlib import Path

from openrecognition.gallery.db import Database
from openrecognition.gallery.recommendations import list_recommendations, sync_pack_recommendations


def _write_pack(root: Path, name: str, body: str) -> None:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "model-pack.yaml").write_text(body)


def test_yaml_packs_import_once_and_db_edits_stick(tmp_path: Path):
    packs = tmp_path / "packs"
    _write_pack(
        packs,
        "edge",
        "name: edge\ndescription: Light set\nmodels:\n  silero_vad:\n    file: silero_vad.onnx\n",
    )
    db = Database(tmp_path / "app.db")
    sync_pack_recommendations(db, packs)
    imported = list_recommendations(db)
    assert imported[0]["id"] == "edge"
    assert imported[0]["label"] == "Edge"
    assert imported[0]["description"] == "Light set"
    assert imported[0]["keys"] == ["silero_vad"]

    with db.connect() as conn:
        conn.execute(
            "UPDATE model_recommendations SET label = ? WHERE id = ?",
            ("Raspberry Pi", "edge"),
        )
        conn.execute(
            """INSERT INTO model_recommendations (id, label, description, sort_order)
               VALUES ('nas', 'NAS', 'Always on', 5)"""
        )
        conn.execute(
            """INSERT INTO model_recommendation_models (recommendation_id, model_key)
               VALUES ('nas', 'face_embedding')"""
        )
        conn.commit()

    _write_pack(
        packs,
        "edge",
        "name: edge\ndescription: Changed later\nmodels:\n  speaker_embedding:\n    file: speaker.onnx\n",
    )
    _write_pack(
        packs,
        "mini",
        "name: mini\ndescription: Mini PC\nmodels:\n  face_detector: optional\n",
    )
    sync_pack_recommendations(db, packs)

    by_id = {row["id"]: row for row in list_recommendations(db)}
    assert by_id["edge"]["label"] == "Raspberry Pi"
    assert by_id["edge"]["description"] == "Light set"
    assert by_id["edge"]["keys"] == ["silero_vad"]
    assert by_id["nas"]["keys"] == ["face_embedding"]
    assert by_id["mini"]["label"] == "Mini"
    assert by_id["mini"]["keys"] == ["face_detector"]
