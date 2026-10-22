"""Choose ONNX vs built-in heuristic inference per user setting."""

from __future__ import annotations

from typing import Any, Literal

from openrecognition.inference.session_pool import ModelSessionPool

InferenceBackend = Literal["auto", "onnx", "heuristic"]

# Slots that can run an ONNX file. The file itself is chosen per category.
KNOWN_MODELS = (
    "silero_vad",
    "speaker_embedding",
    "audio_gate_classifier",
    "face_detector",
    "face_embedding",
    "animal_detector",
    "visual_reid",
)

_IDENTITY_SLOTS = frozenset({"speaker_embedding", "face_embedding", "visual_reid"})


class InferencePolicy:
    """Controls whether ONNX sessions are loaded for each model slot.

    - **auto**: use ONNX when the active model's file is on disk (default).
    - **onnx**: prefer ONNX; fall back to heuristics if a file is missing (with a warning).
    - **heuristic**: never load ONNX, even if weights are present (fast dev / compatibility).
    """

    def __init__(self, pool: ModelSessionPool, backend: InferenceBackend = "auto"):
        self.pool = pool
        self.backend: InferenceBackend = backend

    def set_backend(self, backend: InferenceBackend) -> None:
        self.backend = backend

    def onnx_available(self, model_name: str) -> bool:
        return self.pool.onnx_path(model_name) is not None

    def should_use_onnx(self, model_name: str) -> bool:
        if self.backend == "heuristic":
            return False
        if not self.onnx_available(model_name):
            return False
        return self.backend in ("auto", "onnx")

    def get_session(self, model_name: str) -> Any | None:
        if not self.should_use_onnx(model_name):
            return None
        return self.pool.get_session(model_name)

    def effective_backend(self, model_name: str) -> InferenceBackend | Literal["heuristic"]:
        if self.should_use_onnx(model_name):
            return "onnx"
        return "heuristic"

    def effective_model_version(self, slot: str, heuristic: str) -> str:
        """Version string stored on new embeddings and used for gallery lookup."""
        if self.should_use_onnx(slot):
            ver = self.pool.model_version(slot)
            if ver:
                return ver
        return heuristic

    def _pack_model_slots(self) -> tuple[str, ...]:
        return KNOWN_MODELS

    def fallback_warning(self, model_name: str) -> str | None:
        if model_name not in self._pack_model_slots():
            return None
        if self.onnx_available(model_name):
            return None
        if self.backend == "onnx":
            return (
                f"inference_backend is 'onnx' but {model_name}.onnx is missing "
                "— using heuristic fallback"
            )
        if self.backend == "auto" and model_name in _IDENTITY_SLOTS:
            return (
                f"inference_backend is 'auto' but {model_name}.onnx is missing "
                "— using heuristic fallback"
            )
        return None

    def identity_blocked(self, model_name: str) -> str | None:
        """Refuse speaker/face/visual identify when ONNX was requested and the file is missing."""
        if self.backend != "onnx" or model_name not in _IDENTITY_SLOTS:
            return None
        if self.onnx_available(model_name):
            return None
        return self.fallback_warning(model_name) or f"{model_name}.onnx is missing"

    def status(self) -> dict[str, Any]:
        slots = self._pack_model_slots()
        per_model = {name: self.effective_backend(name) for name in slots}
        any_onnx = any(v == "onnx" for v in per_model.values())
        return {
            "requested": self.backend,
            "effective_summary": "onnx" if any_onnx and self.backend != "heuristic" else "heuristic",
            "models": per_model,
            "warnings": [
                w for name in slots if (w := self.fallback_warning(name)) is not None
            ],
        }
