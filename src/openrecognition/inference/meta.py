"""Inference metadata for API responses."""

from __future__ import annotations

from openrecognition.app_state import AppState


def inference_meta_kwargs(state: AppState) -> dict:
    """Extra MetaInfo fields reflecting ONNX vs heuristic choice."""
    status = state.inference_policy.status()
    warnings = list(status.get("warnings") or [])
    for attr in (
        "last_fallback_warning",
        "last_classifier_fallback_warning",
        "last_face_fallback_warning",
        "last_visual_fallback_warning",
    ):
        for engine in (state.gate, state.speaker, state.vision):
            msg = getattr(engine, attr, None)
            if msg and msg not in warnings:
                warnings.append(msg)
    return {
        "inference_backend": status["requested"],
        "inference_effective": status["effective_summary"],
        "inference_warnings": warnings or None,
    }
