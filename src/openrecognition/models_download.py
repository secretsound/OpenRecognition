"""Download ONNX weights into the models directory."""

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
KnobKind = Literal["int", "float"]


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
    keys: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    tier: TierKind = "recommended"
    sort_order: int = 0


@dataclass(frozen=True)
class KnobField:
    """A setting the operator can change. The contract of the file stays fixed."""

    key: str
    label: str
    kind: KnobKind
    min: float
    max: float
    step: float
    default: float


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
        categories=("speech_check", "voice_match"),
        tier="essential",
        sort_order=1,
    ),
    ModelDownloadPreset(
        id="voice_enhanced",
        label="Voice + gate reasons",
        description=(
            "Speech gate, speaker match, and clearer reject reasons "
            "(music, silence, background noise)."
        ),
        categories=("speech_check", "voice_match", "skip_reasons"),
        tier="recommended",
        sort_order=2,
    ),
    ModelDownloadPreset(
        id="face",
        label="Face recognition",
        description="Identify people from enrollment photos and camera snapshots.",
        categories=("find_face", "match_face"),
        tier="recommended",
        sort_order=3,
    ),
    ModelDownloadPreset(
        id="pets",
        label="Pets & objects",
        description="Recognize enrolled pets or objects. Needs a detector and a visual model.",
        categories=("find_pet", "match_pet"),
        tier="recommended",
        sort_order=4,
    ),
    ModelDownloadPreset(
        id="full",
        label="Suggested for this machine",
        description="The model suggested in every category for the hardware you are on.",
        categories=tuple(category.id for category in MODEL_CATEGORIES),
        tier="recommended",
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
        key="speaker_campplus",
        url=(
            "https://huggingface.co/Wespeaker/wespeaker-voxceleb-campplus/"
            "resolve/main/voxceleb_CAM++.onnx"
        ),
        description="WeSpeaker CAM++ — 512-dim speaker embeddings, about a quarter of the compute (~28 MB)",
        source="huggingface",
        license="Apache-2.0 (WeSpeaker)",
        filename="speaker_campplus.onnx",
        category="voice_match",
        use_for="Recognizes who is speaking.",
        label="WeSpeaker CAM++",
        hardware="pi",
        hardware_note="The one to start with on a Raspberry Pi. Short Assist clips are its strength.",
        version="wespeaker-campplus-voxceleb-v1",
        onnx={
            "preprocessor": "wespeaker_fbank",
            "sample_rate": 16000,
            "num_mel_bins": 80,
            "max_seconds": 15,
            "embed_dim": 512,
        },
        tier="recommended",
        enables=("Voice enrollments", "Recognize → audio", "Wyoming speaker match"),
        depends_on=("silero_vad",),
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
        hardware="mini",
        hardware_note="A steady default on a mini PC. Heavier than CAM++ and a bit more accurate.",
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
        key="speaker_resnet293",
        url=(
            "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet293-LM/"
            "resolve/main/voxceleb_resnet293_LM.onnx"
        ),
        description="WeSpeaker ResNet293 large-margin — 256-dim speaker embeddings (~109 MB)",
        source="huggingface",
        license="Apache-2.0 (WeSpeaker)",
        filename="speaker_resnet293.onnx",
        category="voice_match",
        use_for="Recognizes who is speaking.",
        label="WeSpeaker ResNet293",
        hardware="desktop",
        hardware_note="Best of this set on a desktop. Large-margin training favors clips longer than a few seconds.",
        version="wespeaker-resnet293-lm-v1",
        onnx={
            "preprocessor": "wespeaker_fbank",
            "sample_rate": 16000,
            "num_mel_bins": 80,
            "max_seconds": 15,
            "embed_dim": 256,
        },
        tier="optional",
        enables=("Voice enrollments", "Recognize → audio", "Wyoming speaker match"),
        depends_on=("silero_vad",),
        sort_order=3,
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
        license="Non-commercial research (InsightFace)",
        filename="face_detector.onnx",
        category="find_face",
        use_for="Finds faces in a photo.",
        label="SCRFD",
        hardware="pi",
        version="scrfd-500m",
        onnx={"input_size": 640, "conf_thres": 0.5},
        tier="recommended",
        enables=("Accurate face crops before embedding",),
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
        license="Non-commercial research (InsightFace)",
        filename="face_embedding.onnx",
        category="match_face",
        use_for="Matches a face to someone in the library.",
        label="MobileFace",
        hardware="pi",
        hardware_note="Right size for a Raspberry Pi. A mini PC can step up to ResNet50.",
        version="w600k-mbf-v1",
        onnx={"input_size": 112, "embed_dim": 512, "input_norm": "insightface"},
        tier="essential",
        enables=("Person enrollments with photos", "Recognize → image (face)"),
        depends_on=("face_detector",),
        sort_order=2,
    ),
    ModelDownloadSpec(
        key="face_w600k_r50",
        url=(
            "https://github.com/yakhyo/face-reidentification/releases/download/"
            "v0.0.1/w600k_r50.onnx"
        ),
        description="ResNet50 (w600k_r50) — 512-dim face embeddings (~166 MB)",
        source="github",
        license="Non-commercial research (InsightFace)",
        filename="face_w600k_r50.onnx",
        category="match_face",
        use_for="Matches a face to someone in the library.",
        label="ResNet50",
        hardware="mini",
        hardware_note="Clearer on profile photos and age gaps. Too heavy for a Pi.",
        version="w600k-r50-v1",
        onnx={"input_size": 112, "embed_dim": 512, "input_norm": "insightface"},
        tier="recommended",
        enables=("Person enrollments with photos", "Recognize → image (face)"),
        depends_on=("face_detector",),
        sort_order=3,
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
        enables=("Pet/object region crops (not full-frame guess)",),
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

# Keys an operator may change. Everything else in ``onnx`` is the file's contract.
KNOB_FIELDS: dict[str, tuple[KnobField, ...]] = {
    "speech_check": (
        KnobField("speech_threshold", "Speech threshold", "float", 0.05, 0.95, 0.01, 0.28),
    ),
    "voice_match": (
        KnobField("max_seconds", "Max length (seconds)", "float", 1, 60, 1, 15),
    ),
    "find_face": (
        KnobField("conf_thres", "Minimum score", "float", 0.05, 0.95, 0.05, 0.5),
    ),
    "find_pet": (
        KnobField("conf_thres", "Minimum score", "float", 0.05, 0.95, 0.05, 0.25),
    ),
}


def knob_fields(category: str) -> tuple[KnobField, ...]:
    return KNOB_FIELDS.get(category, ())


def split_settings(category: str, raw: dict | None) -> tuple[dict, dict]:
    """Separate the file contract from the knobs, filling any knob the model omitted."""
    fields = {field.key: field for field in knob_fields(category)}
    source = raw or {}
    contract: dict = {}
    knobs: dict = {}
    for key, value in source.items():
        if key in fields:
            knobs[key] = value
        else:
            contract[key] = value
    for key, field in fields.items():
        knobs.setdefault(key, field.default)
    return contract, knobs


def license_needs_confirm(license_name: str) -> bool:
    text = license_name.lower()
    return "agpl" in text or "non-commercial" in text


def resolve_weight(filename: str, directories: list[Path]) -> Path | None:
    """Find a downloaded file. New files live in the models directory; older packs still count."""
    seen: set[str] = set()
    for directory in directories:
        key = str(directory)
        if key in seen:
            continue
        seen.add(key)
        path = directory / filename
        if path.is_file():
            return path
    return None


def runtime_version(key: str) -> str | None:
    spec = _CATALOG_BY_KEY.get(key)
    if spec is None or not spec.version:
        return None
    return spec.version


def runtime_settings(key: str) -> dict[str, Any]:
    """Contract plus knob defaults. Empty when the key is not in the catalog."""
    spec = _CATALOG_BY_KEY.get(key)
    if spec is None:
        return {}
    contract, knobs = split_settings(spec.category, spec.onnx)
    return {**contract, **knobs}


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


def list_presets(suggested: dict[str, str] | None = None) -> list[dict]:
    """Bundles of the model suggested for each category. Falls back to the built-in default."""
    from openrecognition.model_slots import CATEGORY_SLOT

    chosen = suggested or {}
    out: list[dict] = []
    for preset in sorted(DOWNLOAD_PRESETS, key=lambda x: x.sort_order):
        if preset.categories:
            keys = [
                chosen.get(category) or CATEGORY_SLOT.get(category, "")
                for category in preset.categories
            ]
            keys = [key for key in keys if key]
        else:
            keys = [key for key in preset.keys if key in _CATALOG_BY_KEY]
        if not keys:
            continue
        out.append(
            {
                "id": preset.id,
                "label": preset.label,
                "description": preset.description,
                "keys": keys,
                "tier": preset.tier,
                "sort_order": preset.sort_order,
            }
        )
    return out


def _text_list(value: str | tuple | list) -> list[str]:
    """A one-item sequence written without a trailing comma is a string."""
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


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
        "enables": _text_list(s.enables),
        "depends_on": _text_list(s.depends_on),
        "sort_order": s.sort_order,
    }


def list_catalog(*, pack: str | None = None) -> list[dict]:
    """Human-readable catalog for CLI / API. ``pack`` is ignored."""
    del pack
    specs = list(MODEL_CATALOG)
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


def delete_model_file(
    model_dir: Path,
    key: str,
    *,
    extra_specs: list[ModelDownloadSpec] | None = None,
    search_dirs: list[Path] | None = None,
) -> dict:
    extra = {spec.key: spec for spec in extra_specs or []}
    spec = extra.get(key) or _CATALOG_BY_KEY.get(key)
    if spec is None:
        raise ValueError(f"Unknown model key: {key}")
    directories = search_dirs or [model_dir]
    removed: list[str] = []
    seen: set[str] = set()
    for directory in directories:
        marker = str(directory)
        if marker in seen:
            continue
        seen.add(marker)
        path = directory / spec.onnx_filename
        if path.is_file():
            path.unlink()
            removed.append(path.name)
    if not removed:
        return {"key": key, "status": "missing", "message": "file not on disk"}
    return {"key": key, "status": "deleted", "message": f"removed {spec.onnx_filename}"}


def download_models(
    model_dir: Path,
    *,
    keys: list[str] | None = None,
    force: bool = False,
    extra_specs: list[ModelDownloadSpec] | None = None,
) -> list[dict]:
    """Download models into model_dir. Default: the whole catalog."""
    extra = {spec.key: spec for spec in extra_specs or []}
    if keys:
        specs: list[ModelDownloadSpec] = []
        for key in keys:
            spec = extra.get(key) or _CATALOG_BY_KEY.get(key)
            if spec is None:
                raise ValueError(f"Unknown model key: {key}")
            specs.append(spec)
    else:
        specs = [*MODEL_CATALOG, *extra.values()]
    if not specs:
        raise ValueError("No models to download")

    results: list[dict] = []
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        for spec in specs:
            results.append(
                download_model(spec, model_dir, force=force, client=client)
            )
    return results
