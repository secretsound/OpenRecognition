"""In-process gate + speaker identify for Wyoming utterances."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openrecognition.gallery.match import wyoming_threshold
from openrecognition.integrator.wyoming.wav_util import pcm_to_wav

if TYPE_CHECKING:
    from openrecognition.app_state import AppState


@dataclass
class UtteranceResult:
    gate: str
    accepted: bool
    label: str | None = None
    enrollment_id: str | None = None
    confidence: float | None = None
    recognition_type: str | None = None
    reason: str | None = None
    gate_scores: dict[str, float] | None = None
    candidates: list[dict[str, Any]] | None = None
    min_confidence: float | None = None
    default_min_confidence: float | None = None
    speaker_match_attempted: bool = False
    speaker_model_version: str | None = None
    gallery_count: int = 0
    comparable_speaker_count: int = 0
    sound_events: list[dict[str, Any]] = field(default_factory=list)


def _candidate_rows(candidates: list[dict[str, Any]], *, min_confidence: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidates:
        confidence = float(item.get("confidence") or 0.0)
        label = item.get("label") or "unknown"
        if "accepted" in item:
            accepted = bool(item["accepted"]) and label not in ("unknown", "")
        else:
            accepted = label not in ("unknown", "") and confidence >= min_confidence
        row: dict[str, Any] = {
            "label": label,
            "entity_id": item.get("entity_id"),
            "confidence": confidence,
            "accepted": accepted,
        }
        used = item.get("threshold_used")
        if used is not None:
            row["threshold_used"] = float(used)
        rows.append(row)
    return rows


def _speaker_match(
    state: "AppState",
    wav: bytes,
    *,
    min_confidence: float,
    gate: str,
) -> UtteranceResult:
    """Run speaker embedding + gallery match (independent of gate accept/reject)."""
    if not state.feature_flags.get("biometrics.speaker_enabled", True):
        return UtteranceResult(
            gate=gate,
            accepted=False,
            reason="speaker_disabled",
        )

    from openrecognition.inference.alternates import speaker_alternates

    gallery = state.gallery.get_embeddings_for_match(modality="audio")
    gallery_count = len(gallery)
    if not gallery:
        return UtteranceResult(
            gate=gate,
            accepted=False,
            reason="empty_gallery",
            gallery_count=0,
            comparable_speaker_count=0,
            speaker_match_attempted=True,
            min_confidence=min_confidence,
            default_min_confidence=min_confidence,
            candidates=[],
        )

    outcome = state.speaker.match_retained(
        wav,
        gallery,
        min_confidence,
        True,
        alternates=speaker_alternates(state, gallery),
        threshold_fn=wyoming_threshold,
        top_k=5,
    )
    vec = outcome["vector"]
    comparable_count = int(outcome["comparable"])
    candidates = outcome["candidates"]
    candidate_rows = _candidate_rows(candidates, min_confidence=min_confidence)
    matches = outcome["matches"]

    base = {
        "gate": gate,
        "candidates": candidate_rows,
        "min_confidence": min_confidence,
        "default_min_confidence": min_confidence,
        "speaker_match_attempted": True,
        "gallery_count": gallery_count,
        "comparable_speaker_count": comparable_count,
        "speaker_model_version": outcome["model_version"] or state.speaker.model_version,
    }

    if gate != "accept":
        return UtteranceResult(accepted=False, reason=None, **base)

    if not matches:
        return UtteranceResult(
            accepted=False,
            reason="no_entities",
            **base,
        )

    top = matches[0]
    label = top.get("label")
    confidence = float(top.get("confidence") or 0.0)
    unknown = label in (None, "", "unknown")
    used = top.get("threshold_used")
    accepted = not unknown
    if accepted and used is not None:
        accepted = confidence >= float(used)
    enrollment_id = top.get("entity_id")
    if used is not None:
        base["min_confidence"] = float(used)
    if (
        accepted
        and enrollment_id
        and top.get("type") == "person"
        and vec is not None
        and outcome["model_version"] == state.speaker.current_model_version()
    ):
        from openrecognition.gallery.learn import maybe_learn_voice

        maybe_learn_voice(
            state.gallery,
            enrollment_id,
            vec,
            state.speaker.current_model_version(),
            confidence=confidence,
            candidates=candidates,
            gate_accepted=True,
            dry_run=False,
        )

    return UtteranceResult(
        accepted=accepted,
        label=label,
        enrollment_id=enrollment_id,
        confidence=confidence,
        recognition_type=top.get("recognition_type"),
        reason=None if accepted else "unknown_or_low_confidence",
        **base,
    )


@dataclass
class GatedAudio:
    """Audio gate result, with WAV bytes ready for speaker identification."""

    wav: bytes
    gate: str
    reason: str | None = None
    scores: dict[str, float] | None = None


def gate_utterance(
    state: "AppState",
    pcm: bytes,
    rate: int,
    width: int = 2,
    channels: int = 1,
) -> GatedAudio:
    """Run only the audio gate so the handler can decide whether to call upstream STT."""
    wav = pcm_to_wav(pcm, rate, width, channels)
    gate_resp = state.gate.run(wav)
    return GatedAudio(
        wav=wav,
        gate=gate_resp.gate,
        reason=gate_resp.reason,
        scores=gate_resp.scores,
    )


def identify_wav(
    state: "AppState",
    wav: bytes,
    gate: str,
    reason: str | None,
    scores: dict[str, float] | None,
    *,
    min_confidence: float,
    include_sound_events: bool = False,
) -> UtteranceResult:
    """Speaker match for audio that has already been gated."""
    speaker = _speaker_match(state, wav, min_confidence=min_confidence, gate=gate)
    speaker.gate_scores = scores
    if gate != "accept":
        speaker.reason = reason
        speaker.accepted = False
    if include_sound_events:
        from openrecognition.inference.sound_events import classify_sound_events, wyoming_sound_rows

        policy = getattr(state, "inference_policy", None)
        session = policy.get_session("audio_gate_classifier") if policy is not None else None
        speaker.sound_events = wyoming_sound_rows(classify_sound_events(wav, session=session))
    return speaker


def process_utterance(
    state: "AppState",
    pcm: bytes,
    rate: int,
    width: int = 2,
    channels: int = 1,
    *,
    min_confidence: float,
    block_on_gate_reject: bool = True,
    include_sound_events: bool = False,
) -> UtteranceResult:
    """Run audio gate and speaker match on PCM (same logic as /v1/recognize/audio identify)."""
    del block_on_gate_reject  # handler owns upstream blocking; always identify for logs
    gated = gate_utterance(state, pcm, rate, width, channels)
    return identify_wav(
        state,
        gated.wav,
        gated.gate,
        gated.reason,
        gated.scores,
        min_confidence=min_confidence,
        include_sound_events=include_sound_events,
    )
