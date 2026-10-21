"""Download ONNX model weights into model-packs/<pack>/."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx

SourceKind = Literal["github", "huggingface", "other"]
CategoryId = Literal[
    "speech_check",
    "voice_match",
    "skip_reasons",
    "find_face",
    "match_face",
    "find_pet",
    "match_pet",
]
TierKind = Literal["essential", "recommended", "optional"]
HardwareKind = Literal["pi", "mini", "desktop"]


@dataclass(frozen=True)
class ModelCategory:
    id: CategoryId
    label: str
    description: str
    sort_order: int = 0


@dataclass(frozen=True)
class ModelDownloadPreset:
    """Suggested bundle for a common use case."""

    id: str
    label: str
    description: str
    keys: tuple[str, ...]
    tier: TierKind = "recommended"
    sort_order: int = 0


@dataclass(frozen=True)
class ModelDownloadSpec:
    """One downloadable ONNX artifact."""

    key: str
    url: str
    description: str
    source: SourceKind
    license: str
    category: CategoryId
    use_for: str
    label: str = ""
    hardware: HardwareKind = "pi"
    hardware_note: str = ""
    version: str = ""
    onnx: dict[str, Any] = field(default_factory=dict)
    filename: str = ""
    sha256: str = ""
    packs: tuple[str, ...] = ("edge", "standard", "home")
    tier: TierKind = "recommended"
    enables: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    sort_order: int = 0

    @property
    def onnx_filename(self) -> str:
        return self.filename or f"{self.key}.onnx"


MODEL_CATEGORIES: tuple[ModelCategory, ...] = (
    ModelCategory(
        id="speech_check",
        label="Speech check",
        description="Tells speech apart from noise.",
        sort_order=1,
    ),
    ModelCategory(
        id="voice_match",
        label="Voice match",
        description="Recognizes who is speaking.",
        sort_order=2,
    ),
    ModelCategory(
        id="skip_reasons",
        label="Skip reasons",
        description="Says why a clip was skipped, such as music or silence.",
        sort_order=3,
    ),
    ModelCategory(
        id="find_face",
        label="Find a face",
        description="Finds faces in a photo.",
        sort_order=4,
    ),
    ModelCategory(
        id="match_face",
        label="Match a face",
        description="Matches a face to someone in the library.",
        sort_order=5,
    ),
    ModelCategory(
        id="find_pet",
        label="Find a pet or object",
        description="Finds a pet or object in a photo.",
        sort_order=6,
    ),
    ModelCategory(
        id="match_pet",
        label="Match a pet or object",
        description="Matches a pet or object to the library.",
        sort_order=7,
    ),
)

DOWNLOAD_PRESETS: tuple[ModelDownloadPreset, ...] = (
    ModelDownloadPreset(
        id="voice",
        label="Voice & speaker ID",
        description="Best for Assist / voice pipelines: gate speech, then identify who is speaking.",
        keys=("silero_vad", "speaker_embedding"),
        tier="essential",
        sort_order=1,
    ),
    ModelDownloadPreset(
        id="voice_enhanced",
        label="Voice + gate reasons",
        description=(
            "Silero speech gate plus YAMNet for clearer reject reasons "
            "(music, silence, background noise)."
        ),
        keys=("silero_vad", "speaker_embedding", "audio_gate_classifier"),
        tier="recommended",
        sort_order=2,
    ),
    ModelDownloadPreset(
        id="face",
        label="Face recognition",
        description="Identify people from enrollment photos and camera snapshots.",
        keys=("face_detector", "face_embedding"),
        tier="recommended",
        sort_order=3,
    ),
    ModelDownloadPreset(
        id="pets",
        label="Pets & objects",
        description="Recognize enrolled pets or objects; needs both detector and visual model.",
        keys=("animal_detector", "visual_reid"),
        tier="recommended",
        sort_order=4,
    ),
    ModelDownloadPreset(
        id="full",
        label="Full multimodal",
        description="Voice, faces, pets, and objects. About 65 MB.",
        keys=(
            "silero_vad",
            "speaker_embedding",
            "audio_gate_classifier",
            "face_detector",
            "face_embedding",
            "animal_detector",
            "visual_reid",
        ),
        tier="optional",
        sort_order=5,
    ),
)

# Curated URLs — not committed to git (.gitignore *.onnx).
MODEL_CATALOG: tuple[ModelDownloadSpec, ...] = (
    ModelDownloadSpec(
        key="silero_vad",
        url=(
            "https://github.com/snakers4/silero-vad/raw/master/"
            "src/silero_vad/data/silero_vad.onnx"
        ),
        description="Silero VAD v4 — speech vs non-speech gate",
        source="github",
        license="MIT (Silero)",
        category="speech_check",
        use_for="Tells speech apart from noise.",
        label="Silero VAD",
        hardware="pi",
        version="silero-vad-v4",
        tier="essential",
        enables=("POST /v1/audio/gate", "Early reject on non-speech clips"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="speaker_embedding",
        url=(
            "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34/"
            "resolve/main/voxceleb_resnet34.onnx"
        ),
        description="WeSpeaker ResNet34 — 256-dim speaker embeddings (~26 MB)",
        source="huggingface",
        license="Apache-2.0 (WeSpeaker)",
        category="voice_match",
        use_for="Recognizes who is speaking.",
        label="WeSpeaker ResNet34",
        hardware="pi",
        hardware_note="Fine on a Raspberry Pi. A mini PC is easier when several people talk.",
        version="wespeaker-resnet34-v1",
        onnx={
            "preprocessor": "wespeaker_fbank",
            "sample_rate": 16000,
            "num_mel_bins": 80,
            "max_seconds": 15,
            "embed_dim": 256,
        },
        tier="essential",
        enables=("Voice enrollments", "Recognize → audio", "Wyoming speaker match"),
        depends_on=("silero_vad",),
        sort_order=2,
    ),
    ModelDownloadSpec(
        key="audio_gate_classifier",
        url=(
            "https://huggingface.co/zeropointnine/yamnet-onnx/"
            "resolve/main/yamnet.onnx"
        ),
        description="YAMNet — music / noise / silence labels for gate rejects (~15 MB)",
        source="huggingface",
        license="Apache-2.0 (YAMNet / Google)",
        filename="audio_gate_classifier.onnx",
        category="skip_reasons",
        use_for="Says why a clip was skipped, such as music or silence.",
        label="YAMNet",
        hardware="pi",
        version="yamnet-v1",
        onnx={"sample_rate": 16000, "backend": "yamnet"},
        tier="optional",
        enables=("Gate reason: music", "Gate reason: silence", "Richer gate scores"),
        depends_on=("silero_vad",),
        sort_order=3,
    ),
    ModelDownloadSpec(
        key="face_detector",
        url=(
            "https://github.com/yakhyo/face-reidentification/releases/download/"
            "v0.0.1/det_500m.onnx"
        ),
        description="SCRFD-500M — lightweight face detection (~2.4 MB)",
        source="github",
        license="MIT (InsightFace / SCRFD)",
        filename="face_detector.onnx",
        category="find_face",
        use_for="Finds faces in a photo.",
        label="SCRFD",
        hardware="pi",
        version="scrfd-500m",
        onnx={"input_size": 640, "conf_thres": 0.5},
        tier="recommended",
        enables=("Accurate face crops before embedding"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="face_embedding",
        url=(
            "https://github.com/yakhyo/face-reidentification/releases/download/"
            "v0.0.1/w600k_mbf.onnx"
        ),
        description="MobileFace (w600k_mbf) — 512-dim face embeddings (~13 MB)",
        source="github",
        license="Apache-2.0 (InsightFace)",
        filename="face_embedding.onnx",
        category="match_face",
        use_for="Matches a face to someone in the library.",
        label="MobileFace",
        hardware="pi",
        version="w600k-mbf-v1",
        onnx={"input_size": 112, "embed_dim": 512, "input_norm": "insightface"},
        tier="essential",
        enables=("Person enrollments with photos", "Recognize → image (face)"),
        depends_on=("face_detector",),
        sort_order=2,
    ),
    ModelDownloadSpec(
        key="animal_detector",
        url=(
            "https://github.com/ultralytics/assets/releases/download/"
            "v8.4.0/yolo11n.onnx"
        ),
        description="YOLO11n — pet/object crops for visual re-ID (~5 MB)",
        source="github",
        license="AGPL-3.0 (Ultralytics)",
        filename="animal_detector.onnx",
        category="find_pet",
        use_for="Finds a pet or object in a photo.",
        label="YOLO11",
        hardware="pi",
        version="yolo11n",
        onnx={"input_size": 640, "conf_thres": 0.25},
        tier="recommended",
        enables=("Pet/object region crops (not full-frame guess)"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="visual_reid",
        url=(
            "https://huggingface.co/onnxmodelzoo/mobilenetv2-12-int8/"
            "resolve/main/mobilenetv2-12-int8.onnx"
        ),
        description="MobileNetV2 int8 — 1000-dim visual features for pets/objects (~3.5 MB)",
        source="huggingface",
        license="MIT (ONNX Model Zoo)",
        filename="visual_reid.onnx",
        category="match_pet",
        use_for="Matches a pet or object to the library.",
        label="MobileNetV2",
        hardware="pi",
        version="mobilenetv2-int8-v1",
        onnx={
            "backend": "classifier",
            "input_size": 224,
            "embed_dim": 1000,
            "input_norm": "imagenet",
        },
        tier="essential",
        enables=("Pet/object enrollments", "Recognize → image (pet/object)"),
        depends_on=("animal_detector",),
        sort_order=2,
    ),
)

_CATALOG_BY_KEY = {m.key: m for m in MODEL_CATALOG}


def runtime_version(key: str) -> str | None:
    spec = _CATALOG_BY_KEY.get(key)
    if spec is None or not spec.version:
        return None
    return spec.version


def runtime_settings(key: str) -> dict[str, Any]:
    """How to run a downloaded file. Empty when the key is not in the catalog."""
    spec = _CATALOG_BY_KEY.get(key)
    if spec is None:
        return {}
    return dict(spec.onnx)


def runtime_filename(key: str) -> str:
    spec = _CATALOG_BY_KEY.get(key)
    if spec is None:
        return f"{key}.onnx"
    return spec.onnx_filename


def catalog_for_pack(pack: str) -> list[ModelDownloadSpec]:
    return [m for m in MODEL_CATALOG if pack in m.packs]


def list_categories() -> list[dict]:
    return [
        {
            "id": c.id,
            "label": c.label,
            "description": c.description,
            "sort_order": c.sort_order,
        }
        for c in sorted(MODEL_CATEGORIES, key=lambda x: x.sort_order)
    ]


def list_presets(*, pack: str | None = None) -> list[dict]:
    """Download bundles filtered to keys available in the pack."""
    available = {m.key for m in (catalog_for_pack(pack) if pack else MODEL_CATALOG)}
    out: list[dict] = []
    for preset in sorted(DOWNLOAD_PRESETS, key=lambda x: x.sort_order):
        keys = tuple(k for k in preset.keys if k in available)
        if not keys:
            continue
        out.append(
            {
                "id": preset.id,
                "label": preset.label,
                "description": preset.description,
                "keys": list(keys),
                "tier": preset.tier,
                "sort_order": preset.sort_order,
            }
        )
    return out


def _spec_to_row(s: ModelDownloadSpec) -> dict:
    return {
        "key": s.key,
        "filename": s.onnx_filename,
        "source": s.source,
        "url": s.url,
        "description": s.description,
        "license": s.license,
        "packs": list(s.packs),
        "sha256_pinned": bool(s.sha256),
        "category": s.category,
        "use_for": s.use_for,
        "label": s.label or s.key,
        "version": s.version,
        "onnx": dict(s.onnx),
        "hardware": s.hardware,
        "hardware_note": s.hardware_note,
        "tier": s.tier,
        "enables": list(s.enables),
        "depends_on": list(s.depends_on),
        "sort_order": s.sort_order,
    }


def list_catalog(*, pack: str | None = None) -> list[dict]:
    """Human-readable catalog for CLI / API."""
    specs = catalog_for_pack(pack) if pack else list(MODEL_CATALOG)
    return [_spec_to_row(s) for s in sorted(specs, key=lambda x: (x.category, x.sort_order, x.key))]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_model(
    spec: ModelDownloadSpec,
    pack_dir: Path,
    *,
    force: bool = False,
    client: httpx.Client | None = None,
) -> dict:
    """Download one model. Returns a result dict."""
    dest = pack_dir / spec.onnx_filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        if spec.sha256 and _sha256_file(dest) == spec.sha256:
            return {
                "key": spec.key,
                "path": str(dest),
                "status": "skipped",
                "message": "already present (checksum ok)",
            }
        if not spec.sha256:
            return {
                "key": spec.key,
                "path": str(dest),
                "status": "skipped",
                "message": "already present",
            }

    own_client = client is None
    if own_client:
        client = httpx.Client(follow_redirects=True, timeout=120.0)
    assert client is not None

    try:
        with client.stream("GET", spec.url) as response:
            response.raise_for_status()
            with dest.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
    finally:
        if own_client:
            client.close()

    if spec.sha256 and _sha256_file(dest) != spec.sha256:
        dest.unlink(missing_ok=True)
        raise ValueError(f"checksum mismatch for {dest}")

    size_mb = dest.stat().st_size / (1024 * 1024)
    return {
        "key": spec.key,
        "path": str(dest),
        "status": "downloaded",
        "message": f"saved ({size_mb:.1f} MB) from {spec.source}",
        "source": spec.source,
        "url": spec.url,
    }


def models_status(
    pack_dir: Path,
    *,
    inference: dict | None = None,
    extra_specs: list[ModelDownloadSpec] | None = None,
    active: dict[str, str] | None = None,
) -> dict:
    """Catalog plus on-disk state for admin UI / API."""
    from openrecognition.model_slots import CATEGORY_SLOT

    pack_name = pack_dir.name
    catalog_rows = list_catalog(pack=pack_name)
    for row in catalog_rows:
        row["origin"] = "builtin"
    for spec in extra_specs or []:
        row = _spec_to_row(spec)
        row["origin"] = "custom"
        catalog_rows.append(row)
    order = {c.id: c.sort_order for c in MODEL_CATEGORIES}
    catalog_rows.sort(key=lambda r: (order.get(r["category"], 99), r["sort_order"], r["key"]))
    chosen = active or {}
    catalog: list[dict] = []
    for row in catalog_rows:
        path = pack_dir / row["filename"]
        on_disk = path.exists()
        default_key = CATEGORY_SLOT.get(row["category"])
        is_active = chosen.get(row["category"], default_key) == row["key"]
        entry = {**row, "on_disk": on_disk, "size_bytes": None, "active": is_active}
        if on_disk:
            entry["size_bytes"] = path.stat().st_size
        catalog.append(entry)
    on_disk_keys = {row["key"] for row in catalog if row["on_disk"]}
    presets = []
    for preset in list_presets(pack=pack_name):
        keys = preset["keys"]
        missing = [k for k in keys if k not in on_disk_keys]
        presets.append(
            {
                **preset,
                "complete": len(missing) == 0,
                "missing_keys": missing,
            }
        )
    return {
        "pack": pack_name,
        "pack_dir": str(pack_dir),
        "categories": list_categories(),
        "presets": presets,
        "catalog": catalog,
        "inference": inference,
    }


def delete_model_file(
    pack_dir: Path,
    key: str,
    *,
    extra_specs: list[ModelDownloadSpec] | None = None,
) -> dict:
    extra = {spec.key: spec for spec in extra_specs or []}
    spec = extra.get(key) or _CATALOG_BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"Unknown model key: {key}")
    if key not in extra and pack_dir.name not in spec.packs:
        raise ValueError(f"Model '{key}' is not in pack '{pack_dir.name}'")
    path = pack_dir / spec.onnx_filename
    if not path.exists():
        return {"key": key, "status": "missing", "message": "file not on disk"}
    path.unlink()
    return {"key": key, "status": "deleted", "message": f"removed {path.name}"}


def download_models(
    pack_dir: Path,
    *,
    keys: list[str] | None = None,
    force: bool = False,
    extra_specs: list[ModelDownloadSpec] | None = None,
) -> list[dict]:
    """Download models into pack_dir. Default: all catalog entries for this pack name."""
    pack_name = pack_dir.name
    available = catalog_for_pack(pack_name)
    extra = {spec.key: spec for spec in extra_specs or []}
    if not available and not extra:
        raise ValueError(f"No catalog entries for pack '{pack_name}'")

    if keys:
        specs: list[ModelDownloadSpec] = []
        for key in keys:
            spec = extra.get(key) or _CATALOG_BY_KEY.get(key)
            if spec is None:
                raise ValueError(f"Unknown model key: {key}")
            if key not in extra and pack_name not in spec.packs:
                raise ValueError(f"Model '{key}' is not used in pack '{pack_name}'")
            specs.append(spec)
    else:
        specs = [*available, *extra.values()]

    results: list[dict] = []
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        for spec in specs:
            results.append(
                download_model(spec, pack_dir, force=force, client=client)
            )
    return results
