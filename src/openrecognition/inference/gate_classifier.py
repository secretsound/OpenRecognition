"""YAMNet ONNX gate classifier — music / noise / speech scores for reject reasons."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from openrecognition.inference.audio_gate import resample
from openrecognition.inference.onnx_helpers import run_session
from openrecognition.models.schemas import GateResponse

# AudioSet class indices (YAMNet 521-class head). See yamnet_class_map.csv.
_SPEECH = frozenset(
    {
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        61,
        62,
        63,
        64,
        65,
        66,
    }
)
_MUSIC = frozenset({132}) | frozenset(range(133, 271))
_SILENCE = frozenset({494, 495})
_NOISE = frozenset(
    {
        277,
        279,
        507,
        508,
        509,
        510,
        511,
        513,
        514,
        515,
        321,
        65,
    }
)


def _bucket_scores(frame_scores: np.ndarray) -> dict[str, float]:
    """Mean frame scores aggregated into speech / music / noise."""
    speech = float(np.sum(frame_scores[list(_SPEECH)]))
    music = float(np.sum(frame_scores[list(_MUSIC)]))
    silence = float(np.sum(frame_scores[list(_SILENCE)]))
    noise = float(np.sum(frame_scores[list(_NOISE)]))
    noise_total = noise + silence * 0.5
    total = speech + music + noise_total + 1e-9
    return {
        "speech": speech / total,
        "music": music / total,
        "noise": noise_total / total,
    }


def yamnet_score_matrix(session: Any, audio: np.ndarray, sr: int) -> np.ndarray:
    """Run YAMNet and return per-frame class scores ``(frames, 521)``."""
    audio = resample(audio, sr, 16000)
    if len(audio) < 1600:
        audio = np.pad(audio, (0, 1600 - len(audio)))
    waveform = audio.astype(np.float32)
    inp_name = session.get_inputs()[0].name
    outputs = run_session(session, {inp_name: waveform})
    scores = np.asarray(outputs[0], dtype=np.float32)
    if scores.ndim == 1:
        scores = scores.reshape(1, -1)
    return scores


def yamnet_class_means(session: Any, audio: np.ndarray, sr: int) -> np.ndarray:
    """Mean YAMNet class scores across frames."""
    return yamnet_score_matrix(session, audio, sr).mean(axis=0)


def classify_yamnet(session: Any, audio: np.ndarray, sr: int) -> dict[str, float]:
    """Run YAMNet and return normalized speech/music/noise scores."""
    scores = yamnet_score_matrix(session, audio, sr)
    per_frame = [_bucket_scores(scores[i]) for i in range(scores.shape[0])]
    if not per_frame:
        return {"speech": 0.0, "music": 0.0, "noise": 1.0}
    out = {
        "speech": float(np.mean([p["speech"] for p in per_frame])),
        "music": float(np.mean([p["music"] for p in per_frame])),
        "noise": float(np.mean([p["noise"] for p in per_frame])),
    }
    total = sum(out.values()) + 1e-9
    return {k: v / total for k, v in out.items()}


def _pick_reject_reason(scores: dict[str, float], *, rms: float) -> str:
    if scores["music"] >= 0.35 and scores["music"] > scores["speech"]:
        return "music"
    if rms < 0.005 or (scores["speech"] < 0.08 and scores["noise"] < 0.2):
        return "silence"
    return "background_noise"


def gate_with_yamnet(session: Any, audio: np.ndarray, sr: int) -> GateResponse:
    """Full gate decision from YAMNet alone (when Silero is unavailable)."""
    start = time.perf_counter()
    pcm = resample(audio, sr, 16000)
    if len(pcm) < 1600:
        return GateResponse(
            gate="reject",
            reason="too_short",
            scores={"speech": 0.0, "music": 0.0, "noise": 1.0},
            latency_ms=(time.perf_counter() - start) * 1000,
        )
    scores = classify_yamnet(session, pcm, 16000)
    rms = float(np.sqrt(np.mean(pcm**2))) if len(pcm) else 0.0
    if scores["speech"] >= 0.35 and rms >= 0.01:
        gate, reason = "accept", None
    else:
        gate = "reject"
        reason = _pick_reject_reason(scores, rms=rms)
    return GateResponse(
        gate=gate,
        reason=reason,
        scores=scores,
        latency_ms=(time.perf_counter() - start) * 1000,
    )


def refine_gate_with_classifier(
    session: Any,
    audio: np.ndarray,
    sr: int,
    gate: GateResponse,
) -> GateResponse:
    """Refine reject reason and scores using YAMNet (Silero still owns accept/reject)."""
    start = time.perf_counter()
    pcm = resample(audio, sr, 16000)
    clf_scores = classify_yamnet(session, pcm, 16000)
    rms = float(np.sqrt(np.mean(pcm**2))) if len(pcm) else 0.0

    merged = {
        "speech": (gate.scores.get("speech", 0) + clf_scores["speech"]) / 2,
        "music": clf_scores["music"],
        "noise": clf_scores["noise"],
    }
    total = sum(merged.values()) + 1e-9
    merged = {k: v / total for k, v in merged.items()}

    final_gate = gate.gate
    reason = gate.reason
    # Silero VAD can reject short/quiet speech while YAMNet still sees clear speech — use merged
    # scores for accept so displayed percentages match the decision users see in logs.
    if merged["speech"] >= 0.35 and rms >= 0.01:
        final_gate = "accept"
        reason = None
    elif gate.gate == "reject":
        reason = _pick_reject_reason(clf_scores, rms=rms)

    extra_ms = (time.perf_counter() - start) * 1000
    return GateResponse(
        gate=final_gate,
        reason=reason,
        scores=merged,
        latency_ms=gate.latency_ms + extra_ms,
    )
