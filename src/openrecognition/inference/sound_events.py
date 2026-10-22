"""Sound-event labels for recognize and Wyoming.

Without YAMNet, only speech/music from the heuristic gate are returned.
Doorbell, bark, and glass-break are not guessed from loudness.
When the audio-gate classifier is loaded, YAMNet class scores supply those labels.
"""

from __future__ import annotations

from typing import Any

from openrecognition.inference.audio_gate import heuristic_gate, load_wav_pcm
from openrecognition.models.schemas import EntityResult

# Official YAMNet / AudioSet indices (same map as gate_classifier: 132 is Music).
_EVENT_CLASSES: tuple[tuple[int, str], ...] = (
    (70, "bark"),
    (73, "bark"),
    (352, "glass break"),
    (365, "doorbell"),
    (366, "doorbell"),
    (380, "knock"),
    (326, "siren"),
    (322, "alarm"),
    (398, "telephone"),
    (132, "music"),
)

_EVENT_THRESHOLD = 0.18
_MAX_EVENTS = 4
_WYOMING_SKIP = frozenset({"speech"})


def _entity(label: str, confidence: float) -> EntityResult:
    return EntityResult(
        label=label,
        type="sound",
        recognition_type="sound_event",
        confidence=float(confidence),
        modality="audio",
    )


def _from_yamnet(session: Any, audio, sr: int) -> list[EntityResult]:
    from openrecognition.inference.gate_classifier import yamnet_class_means

    means = yamnet_class_means(session, audio, sr)
    merged: dict[str, float] = {}
    for index, label in _EVENT_CLASSES:
        if index >= len(means):
            continue
        score = float(means[index])
        if score < _EVENT_THRESHOLD:
            continue
        merged[label] = max(merged.get(label, 0.0), score)
    ranked = sorted(merged.items(), key=lambda item: -item[1])[:_MAX_EVENTS]
    return [_entity(label, score) for label, score in ranked]


def _from_heuristic(audio, sr: int) -> list[EntityResult]:
    gate = heuristic_gate(audio, sr)
    entities: list[EntityResult] = []
    if gate.scores.get("speech", 0) > 0.5:
        entities.append(_entity("speech", gate.scores["speech"]))
    if gate.scores.get("music", 0) > 0.45:
        entities.append(_entity("music", gate.scores["music"]))
    return entities


def classify_sound_events(audio_bytes: bytes, *, session: Any | None = None) -> list[EntityResult]:
    audio, sr = load_wav_pcm(audio_bytes)
    if session is not None:
        return _from_yamnet(session, audio, sr)
    return _from_heuristic(audio, sr)


def wyoming_sound_rows(entities: list[EntityResult]) -> list[dict[str, Any]]:
    """Labels worth putting on a Wyoming transcript (skip generic speech)."""
    rows: list[dict[str, Any]] = []
    for item in entities:
        label = (item.label or "").strip()
        if not label or label.lower() in _WYOMING_SKIP:
            continue
        rows.append({"label": label, "confidence": float(item.confidence)})
    return rows
