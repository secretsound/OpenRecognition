"""Embed a clip with a model that enrollments still use, after the active model changes."""

from __future__ import annotations

from openrecognition.gallery.model_registry import runtime_for_version
from openrecognition.inference.speaker import HEURISTIC_MODEL_VERSION, heuristic_speaker_embedding
from openrecognition.inference.vision import (
    FACE_MODEL_VERSION,
    VISUAL_MODEL_VERSION,
    heuristic_visual_embedding,
)


def _versions(gallery: list[dict], types: set[str] | None = None) -> set[str]:
    found: set[str] = set()
    for item in gallery:
        if types is not None and item.get("type") not in types:
            continue
        version = item.get("model_version")
        if version:
            found.add(str(version))
    return found


def _file_embedder(state, category: str, version: str, kind: str):
    target = runtime_for_version(state.db, category, version)
    if target is None:
        return None
    session = state.pool.session_for_file(target["filename"])
    if session is None:
        return None
    cfg = target["settings"]
    if kind == "speaker":
        return lambda audio, session=session, cfg=cfg: state.speaker.embed_configured(
            audio, session=session, cfg=cfg
        )
    if kind == "face":
        return lambda image, session=session, cfg=cfg: state.vision.embed_face_configured(
            image, session=session, cfg=cfg
        )
    return lambda image, bbox=None, session=session, cfg=cfg: state.vision.embed_visual_configured(
        image, bbox, session=session, cfg=cfg
    )


def speaker_alternates(state, gallery: list[dict]) -> dict:
    active = state.speaker.current_model_version()
    out = {}
    for version in _versions(gallery, {"person", "sound"}):
        if version == active:
            continue
        if version == HEURISTIC_MODEL_VERSION:
            from openrecognition.inference.audio_gate import load_wav_pcm

            def embed_heuristic(audio: bytes) -> object:
                pcm, sr = load_wav_pcm(audio)
                return heuristic_speaker_embedding(pcm, sr)

            out[version] = embed_heuristic
            continue
        embedder = _file_embedder(state, "voice_match", version, "speaker")
        if embedder is not None:
            out[version] = embedder
    return out


def face_alternates(state, gallery: list[dict]) -> dict:
    active = state.vision.current_face_model_version()
    out = {}
    for version in _versions(gallery, {"person"}):
        if version == active:
            continue
        if version == FACE_MODEL_VERSION:
            from openrecognition.inference.vision import _image_to_array

            def embed_heuristic(image: bytes) -> object:
                return heuristic_visual_embedding(_image_to_array(image), seed=43)

            out[version] = embed_heuristic
            continue
        embedder = _file_embedder(state, "match_face", version, "face")
        if embedder is not None:
            out[version] = embedder
    return out


def visual_alternates(state, gallery: list[dict]) -> dict:
    active = state.vision.current_visual_model_version()
    out = {}
    for version in _versions(gallery, {"pet", "object"}):
        if version == active:
            continue
        if version == VISUAL_MODEL_VERSION:
            from openrecognition.inference.vision import _image_to_array

            def embed_heuristic(image: bytes, bbox=None) -> object:
                pixels = _image_to_array(image)
                return heuristic_visual_embedding(pixels, seed=44)

            out[version] = embed_heuristic
            continue
        embedder = _file_embedder(state, "match_pet", version, "visual")
        if embedder is not None:
            out[version] = embedder
    return out
