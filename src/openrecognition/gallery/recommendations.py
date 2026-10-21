"""Recommendation sets imported from model-pack.yaml into SQLite.

The active pack file still tells the running server how to load a model.
This table is the list of sets shown on the Models page. A set is imported
once. Later edits in the database are kept, and a new pack folder is added
the next time the list is read.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from openrecognition.gallery.db import Database

logger = logging.getLogger(__name__)

_KNOWN_LABELS = {
    "edge": "Edge",
    "standard": "Standard",
    "home": "Home",
    "pro": "Pro",
}
_KNOWN_ORDER = {"edge": 1, "standard": 2, "home": 3, "pro": 4}


def _label_for(name: str) -> str:
    if name in _KNOWN_LABELS:
        return _KNOWN_LABELS[name]
    return name.replace("_", " ").replace("-", " ").strip().title() or name


def _model_keys(data: dict) -> list[str]:
    models = data.get("models") or {}
    if not isinstance(models, dict):
        return []
    return [str(key) for key in models.keys() if str(key).strip()]


def sync_pack_recommendations(db: Database, packs_dir: Path) -> None:
    """Insert recommendation sets that are not in the database yet."""
    if not packs_dir.is_dir():
        return
    manifests = sorted(path for path in packs_dir.glob("*/model-pack.yaml") if path.is_file())
    with db.connect() as conn:
        for index, path in enumerate(manifests):
            try:
                loaded = yaml.safe_load(path.read_text()) or {}
            except Exception as exc:
                logger.warning("Could not read model pack %s: %s", path, exc)
                continue
            if not isinstance(loaded, dict):
                continue
            rec_id = str(loaded.get("name") or path.parent.name).strip()
            if not rec_id:
                continue
            exists = conn.execute(
                "SELECT 1 FROM model_recommendations WHERE id = ?",
                (rec_id,),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO model_recommendations (id, label, description, sort_order)
                   VALUES (?, ?, ?, ?)""",
                (
                    rec_id,
                    _label_for(rec_id),
                    str(loaded.get("description") or "").strip(),
                    _KNOWN_ORDER.get(rec_id, 100 + index),
                ),
            )
            for key in _model_keys(loaded):
                conn.execute(
                    """INSERT OR IGNORE INTO model_recommendation_models
                       (recommendation_id, model_key) VALUES (?, ?)""",
                    (rec_id, key),
                )
        conn.commit()


def list_recommendations(db: Database) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT id, label, description, sort_order
               FROM model_recommendations
               ORDER BY sort_order, label"""
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            keys = [
                item["model_key"]
                for item in conn.execute(
                    """SELECT model_key FROM model_recommendation_models
                       WHERE recommendation_id = ?
                       ORDER BY model_key""",
                    (row["id"],),
                ).fetchall()
            ]
            out.append(
                {
                    "id": row["id"],
                    "label": row["label"],
                    "description": row["description"],
                    "sort_order": row["sort_order"],
                    "keys": keys,
                }
            )
        return out
