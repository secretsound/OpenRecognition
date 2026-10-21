"""In-process gate + speaker identify for Wyoming utterances."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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
    speaker_match_attempted: bool = False
    speaker_model_version: str | None = None
    gallery_count: int = 0
    comparable_speaker_count: int = 0


def _candidate_rows(candidates: list[dict[str, Any]], *, min_confidence: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidates:
        confidence = float(item.get("confidence") or 0.0)
        label = item.get("label") or "unknown"
        rows.append(
            {
                "label": label,
                "entity_id": item.get("entity_id"),
                "confidence": confidence,
                "accepted": label not in ("unknown", "") and confidence >= min_confidence,
            }
        )
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

    gallery = state.gallery.get_embeddings_for_match(
        modality="audio",
        model_version=state.speaker.current_model_version(),
    )
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
            candidates=[],
        )

    vec = state.speaker.embed(wav)
    comparable = [
        item
        for item in gallery
        if item.get("type") in ("person", "sound") and item["vector"].size == vec.size
    ]
    candidates = state.speaker.match_candidates(vec, gallery, min_confidence, top_k=5)
    candidate_rows = _candidate_rows(candidates, min_confidence=min_confidence)
    matches = state.speaker.match_gallery(
        vec,
        gallery,
        min_confidence,
        return_unknown=True,
    )

    base = {
        "gate": gate,
        "candidates": candidate_rows,
        "min_confidence": min_confidence,
        "speaker_match_attempted": True,
        "gallery_count": gallery_count,
        "comparable_speaker_count": len(comparable),
        "speaker_model_version": state.speaker.model_version,
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
    accepted = not unknown and confidence >= min_confidence
    enrollment_id = top.get("entity_id")
    if accepted and enrollment_id and top.get("type") == "person":
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
) -> UtteranceResult:
    """Speaker match for audio that has already been gated."""
    speaker = _speaker_match(state, wav, min_confidence=min_confidence, gate=gate)
    speaker.gate_scores = scores
    if gate != "accept":
        speaker.reason = reason
        speaker.accepted = False
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
    )
