"""Video enrollment and recognition orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openrecognition.inference.video_demux import (
    VideoDecodeError,
    extract_audio_wav,
    parse_video_modalities,
    sample_frames,
    validate_video_clip,
)
from openrecognition.models.schemas import EntityResult

if TYPE_CHECKING:
    from openrecognition.app_state import AppState


def _limits(state: "AppState") -> dict[str, Any]:
    return state.video_limits()


def _visual_modalities(etype: str, mods: set[str]) -> bool:
    if etype in ("pet", "object"):
        return True
    return "face" in mods or "visual" in mods


def _audio_modalities(etype: str, mods: set[str]) -> bool:
    if etype == "sound":
        return True
    if etype == "person":
        return "audio" in mods or "voice" in mods
    return False


def _max_enrollment_frames(etype: str) -> int:
    return 8 if etype in ("pet", "object") else 6


def process_video_enrollment(
    state: "AppState",
    etype: str,
    data: bytes,
    *,
    video_modalities: str | None = None,
) -> list[tuple[bytes, str, str, str, float | None]]:
    """Return list of (media_bytes, kind, vec_source_kind, modality, timestamp_sec).

    Each item is one embedding sample to store. media_bytes is the bytes stored if retention=keep.
    vec_source_kind is 'audio' or 'image' for embedding path.
    timestamp_sec is set for frame samples, None for audio.
    """
    limits = _limits(state)
    validate_video_clip(
        data,
        max_duration_sec=float(limits["enrollment_max_sec"]),
        max_bytes=int(limits["max_upload_bytes"]),
    )
    mods = parse_video_modalities(video_modalities)
    if etype in ("pet", "object"):
        mods = {"visual"}
    elif etype == "sound":
        mods = {"audio"}

    out: list[tuple[bytes, str, str, str, float | None]] = []

    if _audio_modalities(etype, mods):
        try:
            wav = extract_audio_wav(data)
            from openrecognition.inference.audio_gate import load_wav_pcm

            load_wav_pcm(wav)
            out.append((wav, "audio", "audio", "audio", None))
        except VideoDecodeError:
            if etype == "sound":
                raise
        except Exception:
            if etype == "sound":
                raise VideoDecodeError("No usable audio track in video clip.") from None

    if _visual_modalities(etype, mods):
        frames = sample_frames(data, fps=3.0, max_frames=_max_enrollment_frames(etype))
        step = max(1, len(frames) // _max_enrollment_frames(etype))
        picked = frames[::step][:_max_enrollment_frames(etype)]
        for frame in picked:
            out.append((frame.jpeg_bytes, "image", "image", "image", frame.timestamp_sec))

    if not out:
        raise VideoDecodeError(
            "No usable face, visual, or audio content found in the video clip."
        )
    return out


def recognize_video_bytes(
    state: "AppState",
    data: bytes,
    *,
    min_confidence: float,
    return_unknown: bool,
    video_modalities: str | None = None,
    dry_run: bool = False,
    max_duration_sec: float | None = None,
) -> tuple[list[EntityResult], str | None, str | None, dict[str, float] | None, list[str]]:
    """Returns entities, gate, reason, scores, notes."""
    limits = _limits(state)
    duration_cap = (
        float(limits["recognize_sync_max_sec"])
        if max_duration_sec is None
        else float(max_duration_sec)
    )
    validate_video_clip(
        data,
        max_duration_sec=duration_cap,
        max_bytes=int(limits["max_upload_bytes"]),
    )
    mods = parse_video_modalities(video_modalities)
    entities: list[EntityResult] = []
    notes: list[str] = []
    gate_value: str | None = None
    reason: str | None = None
    scores: dict[str, float] | None = None
    from openrecognition.inference.alternates import (
        face_alternates,
        speaker_alternates,
        visual_alternates,
    )

    audio_gallery = state.gallery.get_embeddings_for_match(modality="audio")
    image_gallery = state.gallery.get_embeddings_for_match(modality="image")

    if "audio" in mods or "voice" in mods:
        try:
            wav = extract_audio_wav(data)
            gate = state.gate.run(wav)
            gate_value = gate.gate
            reason = gate.reason
            scores = gate.scores
            if gate.gate == "accept" and state.feature_flags.get(
                "biometrics.speaker_enabled", True
            ):
                from openrecognition.inference.audio_gate import load_wav_pcm

                audio, sr = load_wav_pcm(wav)
                outcome = state.speaker.match_retained(
                    wav,
                    audio_gallery,
                    min_confidence,
                    return_unknown,
                    alternates=speaker_alternates(state, audio_gallery),
                )
                for m in outcome["matches"]:
                    e = EntityResult(**m)
                    e.time_range = [0.0, len(audio) / sr]
                    e.modality = "audio"
                    entities.append(e)
            elif gate.gate != "accept":
                notes.append("Audio gate rejected — speaker matching skipped.")
        except VideoDecodeError as exc:
            notes.append(str(exc))

    if "face" in mods or "visual" in mods:
        try:
            frames = sample_frames(data, fps=3.0, max_frames=24)
            include_faces = state.feature_flags.get("biometrics.face_enabled", True)
            include_pets = state.feature_flags.get("biometrics.pet_enabled", True)
            seen: dict[str, EntityResult] = {}
            for frame in frames:
                raw, _ = state.vision.recognize_image(
                    frame.jpeg_bytes,
                    image_gallery,
                    include_faces=include_faces,
                    include_pets=include_pets,
                    include_objects=True,
                    min_confidence=min_confidence,
                    return_unknown=return_unknown,
                    include_candidates=False,
                    face_alternates=face_alternates(state, image_gallery),
                    visual_alternates=visual_alternates(state, image_gallery),
                )
                for ent in raw:
                    label = ent["label"]
                    key = f"{ent['recognition_type']}:{label}"
                    ts_end = frame.timestamp_sec + (1.0 / 3.0)
                    existing = seen.get(key)
                    conf = ent["confidence"]
                    if existing is None or conf > existing.confidence:
                        seen[key] = EntityResult(
                            **ent,
                            time_range=[frame.timestamp_sec, ts_end],
                            modality="image",
                        )
            entities.extend(seen.values())
            if not seen and frames:
                notes.append(
                    "Frames were sampled but no faces, pets, or objects matched in the gallery."
                )
        except VideoDecodeError as exc:
            notes.append(str(exc))

    if not entities and not notes:
        notes.append("No matches found in the selected video segment.")

    return entities, gate_value, reason, scores, notes
