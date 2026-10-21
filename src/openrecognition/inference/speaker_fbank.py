"""WeSpeaker-style Kaldi fbank front-end for speaker ONNX models."""

from __future__ import annotations

from typing import Any

import numpy as np

from openrecognition.inference.audio_gate import resample
from openrecognition.inference.onnx_helpers import embedding_from_outputs, l2_normalize, run_session

try:
    import kaldi_native_fbank as knf
except ImportError:
    knf = None  # type: ignore


def compute_fbank(
    audio: np.ndarray,
    sample_rate: int = 16000,
    *,
    num_mel_bins: int = 80,
    frame_length_ms: float = 25.0,
    frame_shift_ms: float = 10.0,
) -> np.ndarray:
    """80-dim log-mel filterbank with per-utterance CMN (matches WeSpeaker ``infer_onnx.py``)."""
    if knf is None:
        raise RuntimeError(
            "kaldi-native-fbank is required for speaker ONNX models. "
            "Install with: pip install kaldi-native-fbank"
        )
    audio = resample(audio.astype(np.float32), sample_rate, 16000)
    # WeSpeaker scales waveform as if int16 before Kaldi fbank.
    scaled = audio * np.float32(1 << 15)

    opts = knf.FbankOptions()
    opts.mel_opts.num_bins = num_mel_bins
    opts.frame_opts.dither = 0.0
    opts.frame_opts.snip_edges = False
    opts.frame_opts.samp_freq = 16000
    opts.frame_opts.frame_length_ms = frame_length_ms
    opts.frame_opts.frame_shift_ms = frame_shift_ms

    fbank = knf.OnlineFbank(opts)
    fbank.accept_waveform(16000, scaled.tolist())
    n = fbank.num_frames_ready
    if n < 1:
        return np.zeros((1, num_mel_bins), dtype=np.float32)
    mat = np.stack([np.array(fbank.get_frame(i), dtype=np.float32) for i in range(n)])
    mat = mat - np.mean(mat, axis=0, keepdims=True)
    return mat


def _trim_audio(audio: np.ndarray, sample_rate: int, max_seconds: float) -> np.ndarray:
    max_samples = int(sample_rate * max_seconds)
    if len(audio) <= max_samples:
        return audio
    start = (len(audio) - max_samples) // 2
    return audio[start : start + max_samples]


def embed_wespeaker_onnx(
    session: Any,
    audio: np.ndarray,
    sr: int,
    *,
    num_mel_bins: int = 80,
    max_seconds: float = 15.0,
    embed_dim: int | None = None,
) -> np.ndarray:
    """Run a WeSpeaker ONNX model (input ``feats`` [B,T,80], output ``embs``)."""
    audio = resample(audio, sr, 16000)
    audio = _trim_audio(audio, 16000, max_seconds)
    feats = compute_fbank(audio, 16000, num_mel_bins=num_mel_bins)
    if feats.shape[0] < 1:
        raise ValueError("Audio too short for speaker embedding")
    tensor = feats[np.newaxis, ...].astype(np.float32)
    outputs = run_session(session, {"feats": tensor})
    emb = embedding_from_outputs(outputs, embed_dim=embed_dim)
    return l2_normalize(emb)
