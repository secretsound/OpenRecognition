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
HardwareKind = Literal["pi", "mini", "desktop", "server"]
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
        key="silero_vad_v6",
        url=(
            "https://github.com/snakers4/silero-vad/raw/v6.2.3/"
            "src/silero_vad/data/silero_vad_16k_op15.onnx"
        ),
        description=(
            "Silero VAD v6.2 — the same speech check, tuned for quiet rooms, "
            "phone calls, and softer voices. MIT license, about 1.3 MB."
        ),
        source="github",
        license="MIT (Silero)",
        filename="silero_vad_v6.onnx",
        category="speech_check",
        use_for="Tells speech apart from noise.",
        label="Silero VAD v6",
        hardware="mini",
        hardware_note="Suggested from a mini PC up. A Pi should stay on v4.",
        version="silero-vad-v6.2.3",
        onnx={"speech_threshold": 0.28},
        tier="recommended",
        enables=("POST /v1/audio/gate", "Early reject on non-speech clips"),
        sort_order=2,
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
        key="speaker_eres2netv2",
        url=(
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "speaker-recongition-models/3dspeaker_speech_eres2netv2_sv_zh-cn_16k-common.onnx"
        ),
        description=(
            "3D-Speaker ERes2NetV2 — 192-number voice embedding, trained on about "
            "200,000 speakers. Apache-2.0, about 68 MB. Strongest on Chinese and "
            "also separates English voices. New samples use this file; people already "
            "enrolled keep matching on the model that saved them."
        ),
        source="github",
        license="Apache-2.0 (3D-Speaker)",
        filename="speaker_eres2netv2.onnx",
        category="voice_match",
        use_for="Recognizes who is speaking.",
        label="ERes2NetV2",
        hardware="server",
        hardware_note="For a home server or a NAS with memory to spare. Too heavy for a desktop.",
        version="eres2netv2-zh-cn-16k",
        onnx={
            "preprocessor": "wespeaker_fbank",
            "sample_rate": 16000,
            "num_mel_bins": 80,
            "max_seconds": 15,
            "embed_dim": 192,
        },
        tier="optional",
        enables=("Voice enrollments", "Recognize → audio", "Wyoming speaker match"),
        depends_on=("silero_vad",),
        sort_order=4,
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
        key="face_yunet",
        url=(
            "https://github.com/opencv/opencv_zoo/raw/main/models/"
            "face_detection_yunet/face_detection_yunet_2023mar.onnx"
        ),
        description=(
            "YuNet (March 2023) — a small face finder from OpenCV Zoo. MIT license, "
            "under 1 MB. It only finds the face; a match model still names the person."
        ),
        source="github",
        license="MIT (OpenCV)",
        filename="face_yunet.onnx",
        category="find_face",
        use_for="Finds faces in a photo.",
        label="YuNet",
        hardware="pi",
        hardware_note="The face finder to start with. MIT license, so it is fine in a product.",
        version="yunet-2023mar",
        onnx={"backend": "yunet", "input_size": 640, "conf_thres": 0.6},
        tier="recommended",
        enables=("Accurate face crops before embedding",),
        sort_order=0,
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
        key="face_scrfd_2_5g",
        url=(
            "https://huggingface.co/hsuyabc/scrfd_2.5g_bnkps.onnx/"
            "resolve/main/scrfd_2.5g_bnkps.onnx"
        ),
        description=(
            "SCRFD-2.5G — a larger InsightFace finder for smaller and turned faces. "
            "About 3 MB. The weights are non-commercial research."
        ),
        source="huggingface",
        license="Non-commercial research (InsightFace)",
        filename="face_scrfd_2_5g.onnx",
        category="find_face",
        use_for="Finds faces in a photo.",
        label="SCRFD 2.5G",
        hardware="mini",
        hardware_note="For a mini PC. The license is research-only, not a product license.",
        version="scrfd-2.5g",
        onnx={"input_size": 640, "conf_thres": 0.5},
        tier="recommended",
        enables=("Accurate face crops before embedding",),
        sort_order=2,
    ),
    ModelDownloadSpec(
        key="face_scrfd_10g",
        url="https://huggingface.co/yakhyo/uniface-weights/resolve/main/scrfd_10g.onnx",
        description=(
            "SCRFD-10G — the accurate InsightFace finder, about 16 MB. "
            "Same file for a desktop and a server. The weights are non-commercial research."
        ),
        source="huggingface",
        license="Non-commercial research (InsightFace)",
        filename="face_scrfd_10g.onnx",
        category="find_face",
        use_for="Finds faces in a photo.",
        label="SCRFD 10G",
        hardware="desktop",
        hardware_note="For a desktop or a server. Detection does not need a larger file than this.",
        version="scrfd-10g",
        onnx={"input_size": 640, "conf_thres": 0.5},
        tier="optional",
        enables=("Accurate face crops before embedding",),
        sort_order=3,
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
        key="face_edgeface_xs",
        url=(
            "https://huggingface.co/yakhyo/uniface-weights/resolve/main/"
            "edgeface_xs_gamma_06.onnx"
        ),
        description=(
            "EdgeFace-XS — a 512-number face embedding built for small machines. "
            "BSD-3-Clause, about 7 MB. Needs a face finder from Find a face. "
            "People already enrolled keep matching on the model that saved them."
        ),
        source="huggingface",
        license="BSD-3-Clause (EdgeFace)",
        filename="face_edgeface_xs.onnx",
        category="match_face",
        use_for="Matches a face to someone in the library.",
        label="EdgeFace XS",
        hardware="pi",
        hardware_note="The face match for a Raspberry Pi. A product-friendly license.",
        version="edgeface-xs-0.6",
        onnx={"input_size": 112, "embed_dim": 512, "input_norm": "insightface"},
        tier="recommended",
        enables=("Person enrollments with photos", "Recognize → image (face)"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="face_adaface_ir50",
        url="https://huggingface.co/yakhyo/uniface-weights/resolve/main/adaface_ir_50.onnx",
        description=(
            "AdaFace IR-50 — 512-number face embedding trained on WebFace4M. "
            "MIT weights, about 166 MB. The training photos themselves can carry "
            "research-only dataset terms. Needs a face finder."
        ),
        source="huggingface",
        license="MIT (AdaFace)",
        filename="face_adaface_ir50.onnx",
        category="match_face",
        use_for="Matches a face to someone in the library.",
        label="AdaFace IR-50",
        hardware="mini",
        hardware_note="Suggested on a mini PC. Clearer than EdgeFace on hard photos.",
        version="adaface-ir50-webface4m",
        onnx={"input_size": 112, "embed_dim": 512, "input_norm": "insightface"},
        tier="recommended",
        enables=("Person enrollments with photos", "Recognize → image (face)"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="face_auraface",
        url="https://huggingface.co/fal/AuraFace-v1/resolve/main/glintr100.onnx",
        description=(
            "AuraFace v1 — a 512-number ResNet-100 face embedding. Apache-2.0, "
            "about 249 MB. Needs a face finder. People already enrolled stay on "
            "the model that created their samples until you add new ones."
        ),
        source="huggingface",
        license="Apache-2.0 (AuraFace)",
        filename="face_auraface.onnx",
        category="match_face",
        use_for="Matches a face to someone in the library.",
        label="AuraFace",
        hardware="desktop",
        hardware_note="The desktop face match. Give it a couple of hundred megabytes of disk.",
        version="auraface-v1",
        onnx={"input_size": 112, "embed_dim": 512, "input_norm": "insightface"},
        tier="recommended",
        enables=("Person enrollments with photos", "Recognize → image (face)"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="face_adaface_ir101",
        url="https://huggingface.co/yakhyo/uniface-weights/resolve/main/adaface_ir_101.onnx",
        description=(
            "AdaFace IR-101 — 512-number face embedding trained on WebFace12M. "
            "MIT weights, about 249 MB. The training set can carry research-only terms. "
            "Needs a face finder."
        ),
        source="huggingface",
        license="MIT (AdaFace)",
        filename="face_adaface_ir101.onnx",
        category="match_face",
        use_for="Matches a face to someone in the library.",
        label="AdaFace IR-101",
        hardware="server",
        hardware_note="For a home server or NAS. The strongest face match in this list.",
        version="adaface-ir101-webface12m",
        onnx={"input_size": 112, "embed_dim": 512, "input_norm": "insightface"},
        tier="optional",
        enables=("Person enrollments with photos", "Recognize → image (face)"),
        sort_order=1,
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
        key="animal_yolo11s",
        url="https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11s.onnx",
        description=(
            "YOLO11s — a larger pet and object finder, about 36 MB. "
            "AGPL-3.0. Same kind of file as YOLO11n, so it drops into the same finder."
        ),
        source="github",
        license="AGPL-3.0 (Ultralytics)",
        filename="yolo11s.onnx",
        category="find_pet",
        use_for="Finds a pet or object in a photo.",
        label="YOLO11s",
        hardware="mini",
        hardware_note="Suggested on a mini PC. AGPL-3.0: shipping this in a product has sharing duties.",
        version="yolo11s",
        onnx={"input_size": 640, "conf_thres": 0.25},
        tier="recommended",
        enables=("Pet/object region crops (not full-frame guess)",),
        sort_order=2,
    ),
    ModelDownloadSpec(
        key="animal_yolo11m",
        url="https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11m.onnx",
        description="YOLO11m — desktop pet and object finder, about 77 MB. AGPL-3.0.",
        source="github",
        license="AGPL-3.0 (Ultralytics)",
        filename="yolo11m.onnx",
        category="find_pet",
        use_for="Finds a pet or object in a photo.",
        label="YOLO11m",
        hardware="desktop",
        hardware_note="Suggested on a desktop. Same AGPL-3.0 license as the smaller YOLO files.",
        version="yolo11m",
        onnx={"input_size": 640, "conf_thres": 0.25},
        tier="optional",
        enables=("Pet/object region crops (not full-frame guess)",),
        sort_order=3,
    ),
    ModelDownloadSpec(
        key="animal_yolo11l",
        url="https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11l.onnx",
        description="YOLO11l — server pet and object finder, about 97 MB. AGPL-3.0.",
        source="github",
        license="AGPL-3.0 (Ultralytics)",
        filename="yolo11l.onnx",
        category="find_pet",
        use_for="Finds a pet or object in a photo.",
        label="YOLO11l",
        hardware="server",
        hardware_note="For a home server or NAS. The largest pet finder in this list.",
        version="yolo11l",
        onnx={"input_size": 640, "conf_thres": 0.25},
        tier="optional",
        enables=("Pet/object region crops (not full-frame guess)",),
        sort_order=4,
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
    ModelDownloadSpec(
        key="visual_dinov2_s",
        url="https://huggingface.co/Xenova/dinov2-small/resolve/main/onnx/model.onnx",
        description=(
            "DINOv2 ViT-S — a 384-number picture embedding from Meta. Apache-2.0, "
            "about 84 MB. It learns the look of a pet or object, not an ImageNet label. "
            "Pets already enrolled stay on MobileNet until you add new samples."
        ),
        source="huggingface",
        license="Apache-2.0 (Meta DINOv2)",
        filename="visual_dinov2_s.onnx",
        category="match_pet",
        use_for="Matches a pet or object to the library.",
        label="DINOv2 Small",
        hardware="mini",
        hardware_note="Suggested on a mini PC. Needs a pet finder from Find a pet or object.",
        version="dinov2-small",
        onnx={
            "backend": "cls",
            "input_size": 224,
            "embed_dim": 384,
            "input_norm": "imagenet",
        },
        tier="recommended",
        enables=("Pet/object enrollments", "Recognize → image (pet/object)"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="visual_dinov2_b",
        url="https://huggingface.co/Xenova/dinov2-base/resolve/main/onnx/model.onnx",
        description=(
            "DINOv2 ViT-B — a 768-number picture embedding. Apache-2.0, about 330 MB. "
            "Same family as the small model, with a sharper match."
        ),
        source="huggingface",
        license="Apache-2.0 (Meta DINOv2)",
        filename="visual_dinov2_b.onnx",
        category="match_pet",
        use_for="Matches a pet or object to the library.",
        label="DINOv2 Base",
        hardware="desktop",
        hardware_note="Suggested on a desktop. Set aside about 330 MB of disk.",
        version="dinov2-base",
        onnx={
            "backend": "cls",
            "input_size": 224,
            "embed_dim": 768,
            "input_norm": "imagenet",
        },
        tier="optional",
        enables=("Pet/object enrollments", "Recognize → image (pet/object)"),
        sort_order=1,
    ),
    ModelDownloadSpec(
        key="visual_dinov2_l",
        url="https://huggingface.co/Xenova/dinov2-large/resolve/main/onnx/model.onnx",
        description=(
            "DINOv2 ViT-L — a 1024-number picture embedding. Apache-2.0, about 1.1 GB. "
            "The strongest pet and object match in this list."
        ),
        source="huggingface",
        license="Apache-2.0 (Meta DINOv2)",
        filename="visual_dinov2_l.onnx",
        category="match_pet",
        use_for="Matches a pet or object to the library.",
        label="DINOv2 Large",
        hardware="server",
        hardware_note="For a home server or NAS. The file is about 1.1 GB.",
        version="dinov2-large",
        onnx={
            "backend": "cls",
            "input_size": 224,
            "embed_dim": 1024,
            "input_norm": "imagenet",
        },
        tier="optional",
        enables=("Pet/object enrollments", "Recognize → image (pet/object)"),
        sort_order=1,
    ),
)

_CATALOG_BY_KEY = {m.key: m for m in MODEL_CATALOG}


@dataclass(frozen=True)
class ModelGuide:
    """Planning facts and the page where someone can read about the model."""

    page_url: str
    disk_bytes: int
    memory_mb: int
    summary: str


# disk_bytes is the file size. memory_mb is a planning figure for RAM once the
# file is loaded, not a benchmark.
MODEL_GUIDE: dict[str, ModelGuide] = {
    "silero_vad": ModelGuide(
        page_url="https://github.com/snakers4/silero-vad",
        disk_bytes=2_327_524,
        memory_mb=64,
        summary=(
            "Listens to a clip and decides whether someone is speaking. "
            "OpenRecognition uses that answer to skip noise before it tries to name a voice. "
            "This is the small file for a Raspberry Pi."
        ),
    ),
    "silero_vad_v6": ModelGuide(
        page_url="https://github.com/snakers4/silero-vad",
        disk_bytes=1_289_603,
        memory_mb=64,
        summary=(
            "Listens to a clip and decides whether someone is speaking, including quieter rooms, "
            "phone calls, and softer voices. It does the same job as the Pi version, with a newer file."
        ),
    ),
    "speaker_campplus": ModelGuide(
        page_url="https://huggingface.co/Wespeaker/wespeaker-voxceleb-campplus",
        disk_bytes=29_292_449,
        memory_mb=400,
        summary=(
            "Turns a voice into a fingerprint and matches it to people you have enrolled. "
            "This is the light voice model, and it is comfortable with the short clips a smart speaker sends."
        ),
    ),
    "speaker_embedding": ModelGuide(
        page_url="https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34",
        disk_bytes=26_534_127,
        memory_mb=500,
        summary=(
            "Turns a voice into a fingerprint and matches it to people you have enrolled. "
            "A step up from CAM++ when the machine has a little more room."
        ),
    ),
    "speaker_resnet293": ModelGuide(
        page_url="https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet293-LM",
        disk_bytes=114_336_285,
        memory_mb=1500,
        summary=(
            "Turns a voice into a fingerprint and matches it to people you have enrolled. "
            "This is the accurate desktop choice. It does its best work with more than a few seconds of speech."
        ),
    ),
    "speaker_eres2netv2": ModelGuide(
        page_url="https://github.com/modelscope/3D-Speaker",
        disk_bytes=71_441_526,
        memory_mb=1500,
        summary=(
            "Turns a voice into a fingerprint and matches it to people you have enrolled. "
            "This is the strongest voice model in the list. It was trained mostly on Chinese speech "
            "and also separates English voices. It asks more of the CPU than the file size suggests."
        ),
    ),
    "audio_gate_classifier": ModelGuide(
        page_url="https://github.com/tensorflow/models/tree/master/research/audioset/yamnet",
        disk_bytes=16_093_603,
        memory_mb=250,
        summary=(
            "Names why a clip was skipped, such as music, silence, or background noise. "
            "It does not say who is speaking."
        ),
    ),
    "face_yunet": ModelGuide(
        page_url="https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet",
        disk_bytes=232_589,
        memory_mb=150,
        summary=(
            "Finds each face in a photo so a match model can look at the face instead of the whole picture. "
            "It is tiny, and the license is fine to ship in a product."
        ),
    ),
    "face_detector": ModelGuide(
        page_url="https://github.com/deepinsight/insightface/tree/master/detection/scrfd",
        disk_bytes=2_524_817,
        memory_mb=300,
        summary=(
            "Finds each face in a photo so a match model can look at the face instead of the whole picture. "
            "A small InsightFace finder. The weights are for non-commercial research."
        ),
    ),
    "face_scrfd_2_5g": ModelGuide(
        page_url="https://github.com/deepinsight/insightface/tree/master/detection/scrfd",
        disk_bytes=3_290_207,
        memory_mb=500,
        summary=(
            "Finds faces in a photo, including smaller ones and faces turned partly away. "
            "A step up from the smallest SCRFD finder. The weights are for non-commercial research."
        ),
    ),
    "face_scrfd_10g": ModelGuide(
        page_url="https://github.com/deepinsight/insightface/tree/master/detection/scrfd",
        disk_bytes=16_923_827,
        memory_mb=800,
        summary=(
            "Finds faces in harder photos: small, turned, or in a busy room. "
            "This is the accurate finder for a desktop or a server. The same file covers both. "
            "The weights are for non-commercial research."
        ),
    ),
    "face_edgeface_xs": ModelGuide(
        page_url="https://github.com/otroshi/edgeface",
        disk_bytes=7_277_264,
        memory_mb=250,
        summary=(
            "Turns a face photo into a fingerprint and matches it to people in the library. "
            "Built for a small machine, and the license is fine to ship in a product. "
            "It needs a face finder from Find a face."
        ),
    ),
    "face_embedding": ModelGuide(
        page_url="https://github.com/yakhyo/face-reidentification",
        disk_bytes=13_616_099,
        memory_mb=300,
        summary=(
            "Turns a face photo into a fingerprint and matches it to people in the library. "
            "A small InsightFace model. The weights are for non-commercial research. "
            "It needs a face finder."
        ),
    ),
    "face_adaface_ir50": ModelGuide(
        page_url="https://github.com/mk-minchul/AdaFace",
        disk_bytes=174_396_180,
        memory_mb=1200,
        summary=(
            "Turns a face photo into a fingerprint and matches it to people in the library. "
            "Clearer than EdgeFace on hard photos. The weights are MIT. "
            "The photos it was trained on can still carry research-only terms."
        ),
    ),
    "face_w600k_r50": ModelGuide(
        page_url="https://github.com/yakhyo/face-reidentification",
        disk_bytes=174_383_860,
        memory_mb=1200,
        summary=(
            "Turns a face photo into a fingerprint and matches it to people in the library. "
            "A larger InsightFace model for a mini PC. The weights are for non-commercial research."
        ),
    ),
    "face_auraface": ModelGuide(
        page_url="https://huggingface.co/fal/AuraFace-v1",
        disk_bytes=260_694_151,
        memory_mb=1600,
        summary=(
            "Turns a face photo into a fingerprint and matches it to people in the library. "
            "This is the desktop face match, and the license is fine to ship in a product. "
            "It needs a face finder."
        ),
    ),
    "face_adaface_ir101": ModelGuide(
        page_url="https://github.com/mk-minchul/AdaFace",
        disk_bytes=260_704_652,
        memory_mb=1800,
        summary=(
            "Turns a face photo into a fingerprint and matches it to people in the library. "
            "This is the strongest face match in the list, for a server or a NAS. "
            "The weights are MIT. The training photos can still carry research-only terms."
        ),
    ),
    "animal_detector": ModelGuide(
        page_url="https://docs.ultralytics.com/models/yolo11/",
        disk_bytes=10_930_182,
        memory_mb=600,
        summary=(
            "Finds a pet or a common object in a photo and crops it before matching. "
            "This is the small finder for a Raspberry Pi. "
            "AGPL-3.0 means sharing duties if you ship this file in a product."
        ),
    ),
    "animal_yolo11s": ModelGuide(
        page_url="https://docs.ultralytics.com/models/yolo11/",
        disk_bytes=38_051_729,
        memory_mb=900,
        summary=(
            "Finds a pet or a common object in a photo and crops it before matching. "
            "A step up from the Pi finder, for a mini PC. Same AGPL-3.0 license."
        ),
    ),
    "animal_yolo11m": ModelGuide(
        page_url="https://docs.ultralytics.com/models/yolo11/",
        disk_bytes=80_673_621,
        memory_mb=1400,
        summary=(
            "Finds a pet or a common object in a photo and crops it before matching. "
            "The desktop finder. It sees smaller pets and busier rooms. Same AGPL-3.0 license."
        ),
    ),
    "animal_yolo11l": ModelGuide(
        page_url="https://docs.ultralytics.com/models/yolo11/",
        disk_bytes=101_744_113,
        memory_mb=1800,
        summary=(
            "Finds a pet or a common object in a photo and crops it before matching. "
            "The largest pet finder in the list, for a server or a NAS. Same AGPL-3.0 license."
        ),
    ),
    "visual_reid": ModelGuide(
        page_url="https://huggingface.co/onnxmodelzoo/mobilenetv2-12-int8",
        disk_bytes=3_655_033,
        memory_mb=200,
        summary=(
            "Turns a pet or object photo into a fingerprint and matches it to the library. "
            "It is a general picture model, so it is the light place to start, not the sharpest match."
        ),
    ),
    "visual_dinov2_s": ModelGuide(
        page_url="https://huggingface.co/Xenova/dinov2-small",
        disk_bytes=88_459_888,
        memory_mb=1200,
        summary=(
            "Turns a pet or object photo into a fingerprint from how the thing looks, not from a fixed list of labels. "
            "This is the mini PC size. Pets already enrolled stay on the previous model until you add a new sample."
        ),
    ),
    "visual_dinov2_b": ModelGuide(
        page_url="https://huggingface.co/Xenova/dinov2-base",
        disk_bytes=346_555_570,
        memory_mb=2200,
        summary=(
            "Turns a pet or object photo into a fingerprint from how the thing looks, not from a fixed list of labels. "
            "The desktop size, sharper than the small model. "
            "Pets already enrolled stay on the previous model until you add a new sample."
        ),
    ),
    "visual_dinov2_l": ModelGuide(
        page_url="https://huggingface.co/Xenova/dinov2-large",
        disk_bytes=1_217_939_460,
        memory_mb=4500,
        summary=(
            "Turns a pet or object photo into a fingerprint from how the thing looks, not from a fixed list of labels. "
            "This is the strongest pet and object match in the list, and the file is large. "
            "Pets already enrolled stay on the previous model until you add a new sample."
        ),
    ),
}


def guide_for(key: str) -> ModelGuide | None:
    return MODEL_GUIDE.get(key)


def public_page(url: str) -> str:
    """A page someone can read. Download links to a raw file are not that page."""
    text = (url or "").strip()
    if not text.startswith(("http://", "https://")):
        return ""
    lowered = text.lower().split("?", 1)[0]
    if "huggingface.co/" in lowered and "/resolve/" in lowered:
        return text.split("/resolve/", 1)[0]
    if "github.com/" in lowered and "/releases/download/" in lowered:
        parts = text.split("/")
        return "/".join(parts[:5]) if len(parts) >= 5 else ""
    if "github.com/" in lowered and "/raw/" in lowered:
        parts = text.split("/")
        return "/".join(parts[:5]) if len(parts) >= 5 else ""
    if lowered.endswith(".onnx"):
        return ""
    return text

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
