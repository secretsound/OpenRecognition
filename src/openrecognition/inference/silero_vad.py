"""Silero VAD ONNX gate (speech vs non-speech)."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from openrecognition.inference.audio_gate import resample
from openrecognition.inference.onnx_helpers import run_session
from openrecognition.models.schemas import GateResponse

# Silero VAD ONNX: 512-sample chunks at 16 kHz; state shape [2, 1, 128].
_CHUNK = 512
_STATE_SHAPE = (2, 1, 128)


def _initial_state() -> np.ndarray:
    return np.zeros(_STATE_SHAPE, dtype=np.float32)


def gate_with_silero(
    session: Any,
    audio: np.ndarray,
    sr: int,
    *,
    speech_threshold: float = 0.28,
) -> GateResponse:
    start = time.perf_counter()
    audio = resample(audio, sr, 16000)
    if len(audio) < _CHUNK:
        audio = np.pad(audio, (0, _CHUNK - len(audio)))

    state = _initial_state()
    probs: list[float] = []
    sr_val = np.array(16000, dtype=np.int64)

    input_names = {i.name for i in session.get_inputs()}
    uses_state = "state" in input_names

    for i in range(0, len(audio) - _CHUNK + 1, _CHUNK):
        chunk = audio[i : i + _CHUNK].astype(np.float32).reshape(1, -1)
        feeds: dict[str, np.ndarray] = {}
        for inp in session.get_inputs():
            name = inp.name
            if name in ("input", "x", "audio"):
                feeds[name] = chunk
            elif name == "sr":
                feeds[name] = sr_val
            elif name == "state" and uses_state:
                feeds[name] = state
            elif name == "h":
                feeds[name] = state[:1] if state.ndim == 3 else state
            elif name == "c":
                feeds[name] = state[1:2] if state.ndim == 3 and state.shape[0] >= 2 else state
        outputs = run_session(session, feeds)
        speech_prob = float(np.asarray(outputs[0]).reshape(-1)[0])
        probs.append(speech_prob)
        if uses_state and len(outputs) >= 2:
            state = np.asarray(outputs[1], dtype=np.float32)
        elif len(outputs) >= 3:
            h = np.asarray(outputs[1], dtype=np.float32)
            c = np.asarray(outputs[2], dtype=np.float32)
            state = np.concatenate([h, c], axis=0)

    speech_ratio = float(np.mean(probs)) if probs else 0.0
    speech_score = min(1.0, speech_ratio * 1.2)
    scores = {
        "speech": speech_score,
        "music": max(0.0, (1.0 - speech_score) * 0.2),
        "noise": max(0.0, 1.0 - speech_score),
    }
    total = sum(scores.values()) + 1e-9
    scores = {k: v / total for k, v in scores.items()}

    if speech_ratio >= speech_threshold:
        gate, reason = "accept", None
    elif scores["noise"] > 0.65:
        gate, reason = "reject", "background_noise"
    else:
        gate, reason = "reject", "silence"

    return GateResponse(
        gate=gate,
        reason=reason,
        scores=scores,
        latency_ms=(time.perf_counter() - start) * 1000,
    )
