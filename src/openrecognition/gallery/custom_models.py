"""Models added from the admin page, stored beside the built-in catalog."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from openrecognition.gallery.db import Database
from openrecognition.model_slots import CATEGORY_SLOT
from openrecognition.models_download import MODEL_CATALOG, MODEL_CATEGORIES, ModelDownloadSpec

_SLUG = re.compile(r"[^a-z0-9]+")


def category_template(category: str) -> ModelDownloadSpec:
    matches = [spec for spec in MODEL_CATALOG if spec.category == category]
    if not matches:
        raise ValueError(f"Unknown category: {category}")
    return matches[0]


def _clean_onnx(category: str, raw: dict | None) -> dict:
    template = category_template(category).onnx
    if not template:
        return {}
    source = raw or {}
    cleaned: dict = {}
    for key, sample in template.items():
        if key not in source or source[key] in (None, ""):
            cleaned[key] = sample
            continue
        value = source[key]
        if isinstance(sample, bool):
            cleaned[key] = bool(value)
        elif isinstance(sample, int) and not isinstance(sample, bool):
            cleaned[key] = int(value)
        elif isinstance(sample, float):
            cleaned[key] = float(value)
        else:
            cleaned[key] = str(value).strip()
    return cleaned


def _validate(label: str, category: str, version: str, url: str) -> tuple[str, str, str]:
    label = label.strip()
    version = version.strip()
    url = url.strip()
    if not label:
        raise ValueError("Name is required")
    if category not in CATEGORY_SLOT:
        raise ValueError("Pick a category")
    if not version:
        raise ValueError("Version is required")
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError("Download link must start with http:// or https://")
    return label, version, url


def _spec_from_row(row) -> ModelDownloadSpec:
    category = row["category"]
    description = next((c.description for c in MODEL_CATEGORIES if c.id == category), "")
    return ModelDownloadSpec(
        key=row["key"],
        url=row["url"],
        description=row["label"],
        source="other",
        license="",
        category=category,
        use_for=row["use_for"] or description,
        label=row["label"],
        version=row["version"],
        onnx=json.loads(row["onnx_json"] or "{}"),
        filename=row["filename"],
        packs=("edge", "standard", "pro", "home"),
        tier="optional",
        sort_order=int(row["sort_order"]),
    )


def list_custom_specs(db: Database) -> list[ModelDownloadSpec]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT key, label, category, version, url, filename, use_for, onnx_json, sort_order
               FROM custom_models ORDER BY sort_order, label"""
        ).fetchall()
    return [_spec_from_row(row) for row in rows]


def active_map(db: Database) -> dict[str, str]:
    with db.connect() as conn:
        rows = conn.execute("SELECT category, model_key FROM active_models").fetchall()
    return {row["category"]: row["model_key"] for row in rows}


def create_custom(
    db: Database,
    *,
    label: str,
    category: str,
    version: str,
    url: str,
    onnx: dict | None = None,
) -> ModelDownloadSpec:
    label, version, url = _validate(label, category, version, url)
    slug = _SLUG.sub("_", label.lower()).strip("_")[:40] or "model"
    key = f"custom_{slug}_{uuid4().hex[:6]}"
    filename = f"{key}.onnx"
    settings = _clean_onnx(category, onnx)
    description = next((c.description for c in MODEL_CATEGORIES if c.id == category), "")
    now = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO custom_models
               (key, label, category, version, url, filename, use_for, onnx_json, sort_order, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (key, label, category, version, url, filename, description, json.dumps(settings), 50, now),
        )
        conn.commit()
    return _spec_from_row(
        {
            "key": key,
            "label": label,
            "category": category,
            "version": version,
            "url": url,
            "filename": filename,
            "use_for": description,
            "onnx_json": json.dumps(settings),
            "sort_order": 50,
        }
    )


def update_custom(
    db: Database,
    key: str,
    *,
    label: str,
    version: str,
    url: str,
    onnx: dict | None = None,
) -> ModelDownloadSpec:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM custom_models WHERE key = ?", (key,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown model key: {key}")
    label, version, url = _validate(label, row["category"], version, url)
    settings = _clean_onnx(row["category"], onnx)
    with db.connect() as conn:
        conn.execute(
            """UPDATE custom_models
               SET label = ?, version = ?, url = ?, onnx_json = ?
               WHERE key = ?""",
            (label, version, url, json.dumps(settings), key),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM custom_models WHERE key = ?", (key,)).fetchone()
    return _spec_from_row(updated)


def delete_custom(db: Database, key: str) -> None:
    with db.connect() as conn:
        row = conn.execute("SELECT key FROM custom_models WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown model key: {key}")
        conn.execute("DELETE FROM custom_models WHERE key = ?", (key,))
        conn.execute("DELETE FROM active_models WHERE model_key = ?", (key,))
        conn.commit()


def set_active(db: Database, category: str, key: str) -> str:
    """Return the inference slot whose loaded file should be dropped."""
    slot = CATEGORY_SLOT.get(category)
    if slot is None:
        raise ValueError("Pick a category")
    if key != slot:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT category FROM custom_models WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None or row["category"] != category:
            raise ValueError("That model is not in this category")
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO active_models (category, model_key) VALUES (?, ?)
               ON CONFLICT(category) DO UPDATE SET model_key = excluded.model_key""",
            (category, key),
        )
        conn.commit()
    return slot


def apply_overrides(pool, db: Database) -> None:
    """Point each built-in slot at the model chosen for that category."""
    chosen = active_map(db)
    customs = {spec.key: spec for spec in list_custom_specs(db)}
    overrides = {}
    for category, slot in CATEGORY_SLOT.items():
        key = chosen.get(category, slot)
        if key == slot:
            continue
        spec = customs.get(key)
        if spec is not None:
            overrides[slot] = spec
    pool.set_slot_overrides(overrides)
