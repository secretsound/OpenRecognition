"""Catalog rows, the one active model per category, and per-model knob overrides.

Built-in models are seeded from code. A later release can add a row without
touching a pack file. Operator tweaks live in ``model_settings`` and never
overwrite the shipped defaults.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from openrecognition.gallery.db import Database
from openrecognition.hardware import TIER_RANK
from openrecognition.model_slots import CATEGORY_SLOT
from openrecognition.models_download import (
    guide_for,
    public_page,
    MODEL_CATALOG,
    MODEL_CATEGORIES,
    ModelDownloadSpec,
    knob_fields,
    license_needs_confirm,
    list_categories,
    list_presets,
    resolve_weight,
    split_settings,
    _text_list,
)

_SLUG = re.compile(r"[^a-z0-9]+")


def _phrase_list(value) -> list[str]:
    """Turn a sentence that was stored one letter at a time back into one line."""
    if isinstance(value, str):
        return [value] if value else []
    items = [str(item) for item in value]
    if len(items) > 1 and all(len(item) <= 1 for item in items):
        return ["".join(items)]
    return items


_IDENTITY = {
    "voice_match": ("audio", None),
    "match_face": ("image", ("person",)),
    "match_pet": ("image", ("pet", "object")),
}


@dataclass
class ModelRecord:
    key: str
    origin: str
    label: str
    category: str
    version: str
    url: str
    filename: str
    license: str
    source: str
    use_for: str
    description: str
    hardware: str
    hardware_note: str
    tier: str
    depends_on: list[str]
    enables: list[str]
    contract: dict
    defaults: dict
    overrides: dict
    sha256: str
    sort_order: int

    @property
    def effective(self) -> dict:
        return {**self.contract, **self.defaults, **self.overrides}

    def as_spec(self) -> ModelDownloadSpec:
        return ModelDownloadSpec(
            key=self.key,
            url=self.url,
            description=self.description or self.label,
            source=self.source if self.source in ("github", "huggingface", "other") else "other",
            license=self.license,
            category=self.category,  # type: ignore[arg-type]
            use_for=self.use_for,
            label=self.label,
            hardware=self.hardware if self.hardware in TIER_RANK else "pi",  # type: ignore[arg-type]
            hardware_note=self.hardware_note,
            version=self.version,
            onnx=self.effective,
            filename=self.filename,
            sha256=self.sha256,
            tier=self.tier if self.tier in ("essential", "recommended", "optional") else "optional",  # type: ignore[arg-type]
            enables=tuple(self.enables),
            depends_on=tuple(self.depends_on),
            sort_order=self.sort_order,
        )


def _loads(raw: str | None, fallback):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _template(category: str) -> ModelDownloadSpec:
    slot = CATEGORY_SLOT.get(category)
    if slot is None:
        raise ValueError(f"Unknown category: {category}")
    for spec in MODEL_CATALOG:
        if spec.key == slot:
            return spec
    raise ValueError(f"Unknown category: {category}")


def _clean_settings(category: str, raw: dict | None) -> dict:
    template = _template(category).onnx
    contract, knobs = split_settings(category, template)
    template_merged = {**contract, **knobs}
    source = raw or {}
    cleaned: dict = {}
    for key, sample in template_merged.items():
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


def _row_to_record(row, overrides: dict) -> ModelRecord:
    return ModelRecord(
        key=row["key"],
        origin=row["origin"],
        label=row["label"],
        category=row["category"],
        version=row["version"],
        url=row["url"],
        filename=row["filename"],
        license=row["license"],
        source=row["source"],
        use_for=row["use_for"],
        description=row["description"],
        hardware=row["hardware"],
        hardware_note=row["hardware_note"],
        tier=row["tier"],
        depends_on=list(_loads(row["depends_on_json"], [])),
        enables=_phrase_list(_loads(row["enables_json"], [])),
        contract=dict(_loads(row["contract_json"], {})),
        defaults=dict(_loads(row["defaults_json"], {})),
        overrides=dict(overrides),
        sha256=row["sha256"] or "",
        sort_order=int(row["sort_order"]),
    )


def sync_catalog(db: Database) -> None:
    """Insert built-in models and refresh their shipped fields. Keep operator overrides."""
    now = _now()
    with db.connect() as conn:
        for spec in MODEL_CATALOG:
            contract, knobs = split_settings(spec.category, spec.onnx)
            conn.execute(
                """INSERT INTO catalog_models (
                       key, origin, label, category, version, url, filename, license, source,
                       use_for, description, hardware, hardware_note, tier, depends_on_json,
                       enables_json, contract_json, defaults_json, sha256, sort_order, created_at
                   ) VALUES (?, 'builtin', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       label = excluded.label,
                       category = excluded.category,
                       version = excluded.version,
                       url = excluded.url,
                       filename = excluded.filename,
                       license = excluded.license,
                       source = excluded.source,
                       use_for = excluded.use_for,
                       description = excluded.description,
                       hardware = excluded.hardware,
                       hardware_note = excluded.hardware_note,
                       tier = excluded.tier,
                       depends_on_json = excluded.depends_on_json,
                       enables_json = excluded.enables_json,
                       contract_json = excluded.contract_json,
                       defaults_json = excluded.defaults_json,
                       sha256 = excluded.sha256,
                       sort_order = excluded.sort_order
                   WHERE catalog_models.origin = 'builtin'""",
                (
                    spec.key,
                    spec.label or spec.key,
                    spec.category,
                    spec.version,
                    spec.url,
                    spec.onnx_filename,
                    spec.license,
                    spec.source,
                    spec.use_for,
                    spec.description,
                    spec.hardware,
                    spec.hardware_note,
                    spec.tier,
                    json.dumps(_text_list(spec.depends_on)),
                    json.dumps(_text_list(spec.enables)),
                    json.dumps(contract),
                    json.dumps(knobs),
                    spec.sha256,
                    spec.sort_order,
                    now,
                ),
            )
        _import_legacy_custom(conn)
        conn.commit()


def _import_legacy_custom(conn) -> None:
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if "custom_models" not in tables:
        return
    rows = conn.execute("SELECT * FROM custom_models").fetchall()
    for row in rows:
        exists = conn.execute(
            "SELECT 1 FROM catalog_models WHERE key = ?",
            (row["key"],),
        ).fetchone()
        if exists:
            continue
        merged = _clean_settings(row["category"], _loads(row["onnx_json"], {}))
        contract, knobs = split_settings(row["category"], merged)
        description = next(
            (c.description for c in MODEL_CATEGORIES if c.id == row["category"]),
            "",
        )
        conn.execute(
            """INSERT INTO catalog_models (
                   key, origin, label, category, version, url, filename, license, source,
                   use_for, description, hardware, hardware_note, tier, depends_on_json,
                   enables_json, contract_json, defaults_json, sha256, sort_order, created_at
               ) VALUES (?, 'custom', ?, ?, ?, ?, ?, '', 'other', ?, ?, 'desktop', '', 'optional',
                         '[]', '[]', ?, ?, '', ?, ?)""",
            (
                row["key"],
                row["label"],
                row["category"],
                row["version"],
                row["url"],
                row["filename"],
                row["use_for"] or description,
                description,
                json.dumps(contract),
                json.dumps(knobs),
                int(row["sort_order"]),
                row["created_at"],
            ),
        )


def _overrides_map(conn) -> dict[str, dict]:
    rows = conn.execute("SELECT model_key, overrides_json FROM model_settings").fetchall()
    return {row["model_key"]: dict(_loads(row["overrides_json"], {})) for row in rows}


def list_records(db: Database) -> list[ModelRecord]:
    with db.connect() as conn:
        overrides = _overrides_map(conn)
        rows = conn.execute(
            "SELECT * FROM catalog_models ORDER BY sort_order, label"
        ).fetchall()
    return [_row_to_record(row, overrides.get(row["key"], {})) for row in rows]


def get_record(db: Database, key: str) -> ModelRecord | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM catalog_models WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        overrides = _overrides_map(conn).get(key, {})
    return _row_to_record(row, overrides)


def active_map(db: Database) -> dict[str, str]:
    with db.connect() as conn:
        rows = conn.execute("SELECT category, model_key FROM active_models").fetchall()
    return {row["category"]: row["model_key"] for row in rows}


def active_key(db: Database, category: str) -> str:
    return active_map(db).get(category) or CATEGORY_SLOT[category]


def suggested_key(records: list[ModelRecord], category: str, tier: str) -> str:
    """Heaviest model in the category that this machine can run."""
    group = [record for record in records if record.category == category]
    if not group:
        return CATEGORY_SLOT[category]
    machine = TIER_RANK.get(tier, 1)
    eligible = [record for record in group if TIER_RANK.get(record.hardware, 0) <= machine]
    pool = eligible or group
    pool.sort(key=lambda record: (-TIER_RANK.get(record.hardware, 0), record.sort_order, record.key))
    return pool[0].key


def fit_for(model_tier: str, machine_tier: str) -> str:
    model_rank = TIER_RANK.get(model_tier, 0)
    machine_rank = TIER_RANK.get(machine_tier, 1)
    if model_rank == machine_rank:
        return "match"
    if model_rank < machine_rank:
        return "lighter"
    return "heavier"


def _identity_count(db: Database, category: str, version: str, *, same: bool) -> int:
    spec = _IDENTITY.get(category)
    if spec is None or not version:
        return 0
    modality, types = spec
    op = "=" if same else "!="
    sql = f"""SELECT COUNT(DISTINCT e.enrollment_id) FROM embeddings e
              JOIN enrollments en ON en.id = e.enrollment_id
              WHERE e.modality = ? AND e.model_version {op} ?"""
    params: list = [modality, version]
    if types:
        sql += f" AND en.type IN ({','.join('?' for _ in types)})"
        params.extend(types)
    with db.connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def reenroll_count(db: Database, category: str, version: str) -> int:
    """Enrollments whose saved vectors were made with a different model."""
    return _identity_count(db, category, version, same=False)


def enrollment_count(db: Database, category: str, version: str) -> int:
    """Enrollments that still match with this model's saved vectors."""
    return _identity_count(db, category, version, same=True)


def runtime_for_version(db: Database, category: str, version: str) -> dict | None:
    """File and settings for a model version that enrollments may still use."""
    for record in list_records(db):
        if record.category == category and record.version == version:
            return {
                "key": record.key,
                "filename": record.filename,
                "settings": record.effective,
                "version": record.version,
                "label": record.label,
            }
    return None


def removal_block_reason(db: Database, key: str) -> str | None:
    """Why this model's file must stay, or None when it can be removed."""
    record = get_record(db, key)
    if record is None:
        return None
    count = enrollment_count(db, record.category, record.version)
    if count == 0:
        return None
    noun = "enrollment" if count == 1 else "enrollments"
    verb = "uses" if count == 1 else "use"
    return (
        f"{count} {noun} still {verb} {record.label}. "
        "Add samples with the new model before removing this one."
    )


def set_active(db: Database, category: str, key: str) -> str:
    """Point the category at a model. Returns the inference slot to unload."""
    slot = CATEGORY_SLOT.get(category)
    if slot is None:
        raise ValueError("Pick a category")
    sync_catalog(db)
    record = get_record(db, key)
    if record is None or record.category != category:
        raise ValueError("That model is not in this category")
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO active_models (category, model_key) VALUES (?, ?)
               ON CONFLICT(category) DO UPDATE SET model_key = excluded.model_key""",
            (category, key),
        )
        conn.commit()
    return slot


def bind_active(pool, db: Database) -> None:
    """Tell the session pool which file and settings each slot should use."""
    sync_catalog(db)
    chosen = active_map(db)
    records = {record.key: record for record in list_records(db)}
    active: dict[str, dict] = {}
    for category, slot in CATEGORY_SLOT.items():
        key = chosen.get(category, slot)
        record = records.get(key)
        if record is None:
            continue
        active[slot] = {
            "key": record.key,
            "version": record.version,
            "filename": record.filename,
            "settings": record.effective,
        }
    pool.set_active_models(active)


def maybe_activate_download(
    db: Database,
    directories: list[Path],
    key: str,
    *,
    alone: bool,
    tier: str,
) -> bool:
    """Use a newly downloaded model when the category has no file and no saved vectors."""
    record = get_record(db, key)
    if record is None:
        return False
    records = list_records(db)
    suggested = suggested_key(records, record.category, tier)
    if key != suggested and not alone:
        return False
    current = active_key(db, record.category)
    if current == key:
        return False
    current_record = get_record(db, current)
    if current_record is not None and resolve_weight(current_record.filename, directories):
        return False
    if reenroll_count(db, record.category, record.version) > 0:
        return False
    set_active(db, record.category, key)
    return True


def _coerce_knob(field, value):
    if field.kind == "int":
        number = int(value)
    else:
        number = float(value)
    if number < field.min or number > field.max:
        raise ValueError(f"{field.label} must be between {field.min:g} and {field.max:g}")
    return number


def _coerce_contract(sample, value):
    """Keep the shipped type when an operator edits an ONNX field."""
    if isinstance(sample, bool):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(sample, int):
        return int(value)
    if isinstance(sample, float):
        return float(value)
    return str(value).strip()


def update_knobs(db: Database, key: str, overrides: dict) -> ModelRecord:
    sync_catalog(db)
    record = get_record(db, key)
    if record is None:
        raise ValueError(f"Unknown model key: {key}")
    fields = {field.key: field for field in knob_fields(record.category)}
    contract = record.contract
    if not fields and not contract:
        raise ValueError("This model has no adjustable settings")
    merged = dict(record.overrides)
    for name, value in overrides.items():
        if name in fields:
            if value is None:
                merged.pop(name, None)
                continue
            merged[name] = _coerce_knob(fields[name], value)
            continue
        if name in contract:
            if value is None:
                merged.pop(name, None)
                continue
            merged[name] = _coerce_contract(contract[name], value)
            continue
        raise ValueError(f"{name} is not a setting for this model")
    with db.connect() as conn:
        if merged:
            conn.execute(
                """INSERT INTO model_settings (model_key, overrides_json) VALUES (?, ?)
                   ON CONFLICT(model_key) DO UPDATE SET overrides_json = excluded.overrides_json""",
                (key, json.dumps(merged)),
            )
        else:
            conn.execute("DELETE FROM model_settings WHERE model_key = ?", (key,))
        conn.commit()
    updated = get_record(db, key)
    assert updated is not None
    return updated


def reset_knobs(db: Database, key: str) -> ModelRecord:
    if get_record(db, key) is None:
        raise ValueError(f"Unknown model key: {key}")
    with db.connect() as conn:
        conn.execute("DELETE FROM model_settings WHERE model_key = ?", (key,))
        conn.commit()
    updated = get_record(db, key)
    assert updated is not None
    return updated


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
    sync_catalog(db)
    merged = _clean_settings(category, onnx)
    contract, knobs = split_settings(category, merged)
    slug = _SLUG.sub("_", label.lower()).strip("_")[:40] or "model"
    key = f"custom_{slug}_{uuid4().hex[:6]}"
    filename = f"{key}.onnx"
    description = next((c.description for c in MODEL_CATEGORIES if c.id == category), "")
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO catalog_models (
                   key, origin, label, category, version, url, filename, license, source,
                   use_for, description, hardware, hardware_note, tier, depends_on_json,
                   enables_json, contract_json, defaults_json, sha256, sort_order, created_at
               ) VALUES (?, 'custom', ?, ?, ?, ?, ?, '', 'other', ?, ?, 'desktop', '', 'optional',
                         '[]', '[]', ?, ?, '', 50, ?)""",
            (
                key,
                label,
                category,
                version,
                url,
                filename,
                description,
                description,
                json.dumps(contract),
                json.dumps(knobs),
                _now(),
            ),
        )
        conn.commit()
    record = get_record(db, key)
    assert record is not None
    return record.as_spec()


def update_custom(
    db: Database,
    key: str,
    *,
    label: str,
    version: str,
    url: str,
    onnx: dict | None = None,
) -> ModelDownloadSpec:
    record = get_record(db, key)
    if record is None:
        raise ValueError(f"Unknown model key: {key}")
    if record.origin != "custom":
        raise ValueError("Built-in models are edited from their settings")
    label, version, url = _validate(label, record.category, version, url)
    merged = _clean_settings(record.category, onnx)
    contract, knobs = split_settings(record.category, merged)
    with db.connect() as conn:
        conn.execute(
            """UPDATE catalog_models
               SET label = ?, version = ?, url = ?, contract_json = ?, defaults_json = ?
               WHERE key = ?""",
            (label, version, url, json.dumps(contract), json.dumps(knobs), key),
        )
        conn.commit()
    updated = get_record(db, key)
    assert updated is not None
    return updated.as_spec()


def delete_custom(db: Database, key: str) -> None:
    record = get_record(db, key)
    if record is None:
        raise ValueError(f"Unknown model key: {key}")
    if record.origin != "custom":
        raise ValueError("Built-in models stay in the catalog")
    with db.connect() as conn:
        conn.execute("DELETE FROM catalog_models WHERE key = ?", (key,))
        conn.execute("DELETE FROM model_settings WHERE model_key = ?", (key,))
        conn.execute("DELETE FROM active_models WHERE model_key = ?", (key,))
        conn.commit()


def list_custom_specs(db: Database) -> list[ModelDownloadSpec]:
    return [record.as_spec() for record in list_records(db) if record.origin == "custom"]


def slot_for_active_key(db: Database, key: str) -> str | None:
    record = get_record(db, key)
    if record is None:
        return None
    if active_key(db, record.category) != key:
        return None
    return CATEGORY_SLOT.get(record.category)


def build_status(
    db: Database,
    *,
    model_dir: Path,
    search_dirs: list[Path],
    tier: str,
    hardware: dict,
    threads: dict,
    inference: dict | None,
    inference_backend: str,
) -> dict:
    sync_catalog(db)
    records = list_records(db)
    by_key = {record.key: record for record in records}
    suggestions = {
        category: suggested_key(records, category, tier) for category in CATEGORY_SLOT
    }
    catalog: list[dict] = []
    for record in sorted(records, key=lambda item: (item.category, item.sort_order, item.label)):
        path = resolve_weight(record.filename, search_dirs)
        fields = []
        for field in knob_fields(record.category):
            overridden = field.key in record.overrides
            raw_default = record.defaults.get(field.key, field.default)
            value = record.overrides[field.key] if overridden else raw_default
            fields.append(
                {
                    "key": field.key,
                    "label": field.label,
                    "kind": field.kind,
                    "min": field.min,
                    "max": field.max,
                    "step": field.step,
                    "default": raw_default,
                    "value": value,
                    "overridden": overridden,
                }
            )
        guide = guide_for(record.key)
        catalog.append(
            {
                "key": record.key,
                "filename": record.filename,
                "source": record.source,
                "url": record.url,
                "page_url": guide.page_url if guide else public_page(record.url),
                "description": guide.summary if guide else record.description,
                "disk_bytes": guide.disk_bytes if guide else 0,
                "memory_mb": guide.memory_mb if guide else 0,
                "license": record.license,
                "license_warning": license_needs_confirm(record.license),
                "on_disk": path is not None,
                "size_bytes": path.stat().st_size if path is not None else None,
                "category": record.category,
                "use_for": record.use_for,
                "label": record.label,
                "version": record.version,
                "onnx": record.effective,
                "contract": record.contract,
                "knobs": fields,
                "hardware": record.hardware,
                "hardware_note": record.hardware_note,
                "fit": fit_for(record.hardware, tier),
                "suggested": suggestions.get(record.category) == record.key,
                "tier": record.tier,
                "enables": record.enables,
                "depends_on": record.depends_on,
                "sort_order": record.sort_order,
                "origin": record.origin,
                "active": active_key(db, record.category) == record.key,
                "reenroll_count": reenroll_count(db, record.category, record.version),
                "enrollment_count": enrollment_count(db, record.category, record.version),
                "sha256_pinned": bool(record.sha256),
            }
        )
    on_disk = {row["key"] for row in catalog if row["on_disk"]}
    presets = []
    for preset in list_presets(suggestions):
        missing = [key for key in preset["keys"] if key not in on_disk]
        presets.append({**preset, "complete": not missing, "missing_keys": missing})
    return {
        "models_dir": str(model_dir),
        "hardware": hardware,
        "threads": threads,
        "categories": list_categories(),
        "presets": presets,
        "catalog": catalog,
        "inference_backend": inference_backend,
        "inference": inference,
        "by_key": by_key,
    }
