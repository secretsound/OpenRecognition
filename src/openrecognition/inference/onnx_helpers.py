"""Shared ONNX Runtime helpers."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None  # type: ignore


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    v = vec.astype(np.float32).flatten()
    norm = np.linalg.norm(v)
    if norm > 1e-9:
        v = v / norm
    return v


def run_session(session: Any, feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
    input_names = {i.name for i in session.get_inputs()}
    filtered = {k: v for k, v in feeds.items() if k in input_names}
    outputs = session.run(None, filtered)
    return outputs


def first_output_array(outputs: list[Any]) -> np.ndarray:
    for out in outputs:
        if isinstance(out, np.ndarray):
            return out
    raise RuntimeError("ONNX session returned no ndarray output")


def inspect_session(session: Any) -> dict[str, Any]:
    return {
        "inputs": [
            {"name": i.name, "shape": i.shape, "type": i.type}
            for i in session.get_inputs()
        ],
        "outputs": [
            {"name": o.name, "shape": o.shape, "type": o.type}
            for o in session.get_outputs()
        ],
    }


def embedding_from_outputs(outputs: list[Any], *, embed_dim: int | None = None) -> np.ndarray:
    """Pick a flat embedding vector from typical speaker/face ONNX outputs."""
    arrays = [o for o in outputs if isinstance(o, np.ndarray)]
    if not arrays:
        raise RuntimeError("No tensor outputs from embedding model")
    # Prefer 2D (batch, dim) or 1D (dim,)
    ranked = sorted(arrays, key=lambda a: (-a.ndim, -a.size))
    vec = ranked[0]
    if vec.ndim > 1:
        vec = vec[0]
    vec = vec.astype(np.float32).flatten()
    if embed_dim is not None and vec.size != embed_dim:
        if vec.size > embed_dim:
            vec = vec[:embed_dim]
        else:
            vec = np.pad(vec, (0, embed_dim - vec.size))
    return l2_normalize(vec)
