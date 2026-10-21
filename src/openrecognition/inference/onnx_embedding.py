"""Generic waveform / image ONNX embedding runners."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from openrecognition.inference.audio_gate import resample
from openrecognition.inference.onnx_helpers import embedding_from_outputs, run_session


def embed_audio_waveform(
    session: Any,
    audio: np.ndarray,
    sr: int,
    *,
    sample_rate: int = 16000,
    min_samples: int = 4800,
    embed_dim: int | None = None,
) -> np.ndarray:
    audio = resample(audio, sr, sample_rate)
    if len(audio) < min_samples:
        audio = np.pad(audio, (0, min_samples - len(audio)))
    feeds: dict[str, np.ndarray] = {}
    for inp in session.get_inputs():
        name = inp.name
        if name in ("input", "audio", "waveform", "x"):
            feeds[name] = audio.astype(np.float32).reshape(1, -1)
        elif name == "sr":
            feeds[name] = np.array([sample_rate], dtype=np.int64)
    outputs = run_session(session, feeds)
    return embedding_from_outputs(outputs, embed_dim=embed_dim)


def _image_tensor(
    pixels: np.ndarray,
    *,
    size: int,
    input_norm: str,
) -> np.ndarray:
    img = Image.fromarray((np.clip(pixels, 0, 1) * 255).astype(np.uint8))
    img = img.resize((size, size), Image.Resampling.BILINEAR)
    arr = np.array(img, dtype=np.float32)
    if input_norm == "insightface":
        tensor = (arr - 127.5) / 127.5
    elif input_norm == "imagenet":
        arr /= 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = (arr - mean) / std
    else:
        arr /= 255.0
        tensor = (arr - 0.5) / 0.5
    return np.transpose(tensor, (2, 0, 1))[np.newaxis, ...].astype(np.float32)


def embed_image_nchw(
    session: Any,
    pixels: np.ndarray,
    *,
    size: int = 112,
    embed_dim: int | None = None,
    input_norm: str = "half",
) -> np.ndarray:
    """Run a face/re-ID model expecting NCHW float input."""
    tensor = _image_tensor(pixels, size=size, input_norm=input_norm)
    feeds: dict[str, np.ndarray] = {}
    for inp in session.get_inputs():
        if inp.name in ("input", "data", "image", "input.1"):
            feeds[inp.name] = tensor
    outputs = run_session(session, feeds)
    return embedding_from_outputs(outputs, embed_dim=embed_dim)


def embed_image_classifier(
    session: Any,
    pixels: np.ndarray,
    *,
    size: int = 224,
    embed_dim: int | None = None,
    input_norm: str = "imagenet",
) -> np.ndarray:
    """ImageNet-style classifier ONNX → L2-normalized embedding (logits or penultimate)."""
    tensor = _image_tensor(pixels, size=size, input_norm=input_norm)
    feeds: dict[str, np.ndarray] = {}
    for inp in session.get_inputs():
        if inp.name in ("input", "data", "image", "input.1"):
            feeds[inp.name] = tensor
    outputs = run_session(session, feeds)
    return embedding_from_outputs(outputs, embed_dim=embed_dim)
