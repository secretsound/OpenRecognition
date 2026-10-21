"""Enrollment CRUD."""

import io
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile  # noqa: F401
from PIL import Image, UnidentifiedImageError

from openrecognition.api.deps import get_request_id, get_state, require_scope
from openrecognition.api.errors import bad_request, not_found
from openrecognition.app_state import AppState
from openrecognition.gallery.sample_meta import SampleMeta, parse_sample_meta_form
from openrecognition.inference.video_demux import VideoDecodeError, is_video_container
from openrecognition.models.schemas import (
    EnrollmentCreate,
    EnrollmentOut,
    EnrollmentPatch,
    EnrollmentType,
    QualityInfo,
    SampleOut,
)
from openrecognition.pipelines.video import process_video_enrollment

router = APIRouter(prefix="/v1/enrollments", tags=["enrollments"])

_AUDIO_TYPES = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp3",
        "audio/flac",
        "audio/ogg",
        "audio/webm",
        "audio/mp4",
        "audio/aac",
        "audio/x-m4a",
    }
)
_IMAGE_TYPES = frozenset(
    {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif", "image/bmp"}
)


def _detect_media_kind(data: bytes, content_type: str | None, filename: str | None) -> str:
    from openrecognition.inference.audio_gate import AudioDecodeError, load_wav_pcm

    if is_video_container(data, content_type, filename):
        return "video"
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in _AUDIO_TYPES:
        try:
            load_wav_pcm(data)
            return "audio"
        except AudioDecodeError as exc:
            raise bad_request("INVALID_MEDIA", str(exc)) from exc
    if ct in _IMAGE_TYPES:
        return "image"
    name = (filename or "").lower()
    if name.endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".webm")):
        return "audio"
    if name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")):
        return "image"
    if data[:4] == b"RIFF" or data[:3] == b"ID3" or data[:4] == b"fLaC" or data[:4] == b"OggS":
        return "audio"
    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff":
        return "image"
    try:
        Image.open(io.BytesIO(data)).verify()
        return "image"
    except (UnidentifiedImageError, OSError):
        pass
    try:
        load_wav_pcm(data)
        return "audio"
    except AudioDecodeError:
        pass
    raise bad_request(
        "UNSUPPORTED_MEDIA",
        "Could not detect media type; use audio (WAV, MP3, …) or image (JPEG, PNG, WebP).",
    )


def _form_bool(value: str | None, *, default: bool = True) -> bool:
    """Parse a form checkbox.

    FastAPI treats a missing ``bool`` form field as ``False`` and ignores the
    declared default, so an omitted ``enabled`` would create a gallery row that
    recognition never sees. Accept the string and apply ``default`` when absent.
    """
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _audio_duration_ms(data: bytes) -> float | None:
    from openrecognition.inference.audio_gate import AudioDecodeError, load_wav_pcm

    try:
        audio, sr = load_wav_pcm(data)
        return len(audio) / sr * 1000.0
    except AudioDecodeError:
        return None


def _embed_sample(
    state: AppState,
    etype: str,
    data: bytes,
    kind: str,
) -> tuple:
    if etype in ("pet", "object"):
        if kind != "image":
            raise bad_request(
                "INVALID_MEDIA",
                f"{etype} enrollments require image files (JPEG, PNG, WebP).",
            )
        return state.vision.embed_visual(data), state.vision.visual_model_version, "image"
    if etype == "sound":
        if kind != "audio":
            raise bad_request(
                "INVALID_MEDIA",
                "Sound enrollments require audio files (WAV, MP3, FLAC, OGG).",
            )
        return state.speaker.embed(data), state.speaker.model_version, "audio"
    # person: voice and/or face
    if kind == "audio":
        return state.speaker.embed(data), state.speaker.model_version, "audio"
    if kind == "image":
        return state.vision.embed_face(data), state.vision.face_model_version, "image"
    raise bad_request("INVALID_MEDIA", "Unsupported file for person enrollment.")


def _resolve_sample_meta(
    f: UploadFile,
    data: bytes,
    kind: str,
    index: int,
    meta_list: list[SampleMeta | None],
    *,
    default_source: str,
) -> SampleMeta:
    if index < len(meta_list) and meta_list[index] is not None:
        meta = meta_list[index]
        assert meta is not None
        if not meta.original_filename and f.filename:
            meta.original_filename = f.filename
        if not meta.content_type and f.content_type:
            meta.content_type = f.content_type
        if meta.size_bytes is None:
            meta.size_bytes = len(data)
        if kind == "audio" and meta.duration_ms is None:
            meta.duration_ms = _audio_duration_ms(data)
        return meta
    duration = _audio_duration_ms(data) if kind == "audio" else None
    return SampleMeta.from_upload(
        filename=f.filename,
        content_type=f.content_type,
        size_bytes=len(data),
        duration_ms=duration,
        source=default_source,
    )


def _log_enrollment(
    state: AppState,
    event: str,
    en: dict,
    *,
    auth: dict | None,
    summary: str,
) -> None:
    state.recognition_logs.record(
        event=event,
        modality="enrollment",
        label=en.get("label"),
        entity_id=en.get("id"),
        summary=summary,
        auth=auth,
    )


def _to_out(en: dict, quality: QualityInfo | None = None, dup: str | None = None) -> EnrollmentOut:
    return EnrollmentOut(
        id=en["id"],
        type=EnrollmentType(en["type"]),
        label=en["label"],
        species_hint=en.get("species_hint"),
        enabled=en["enabled"],
        threshold=en.get("threshold"),
        learn_enabled=bool(en.get("learn_enabled")),
        learn_min_confidence=float(en.get("learn_min_confidence") or 0.9),
        learn_margin=float(en.get("learn_margin") or 0.0),
        learn_daily_cap=int(en.get("learn_daily_cap") or 0),
        learn_max_samples=int(en.get("learn_max_samples") or 1),
        external_ids=en.get("external_ids") or {},
        sample_count=en["sample_count"],
        model_version=en.get("model_version"),
        created_at=en["created_at"],
        updated_at=en["updated_at"],
        quality=quality,
        duplicate_warning=dup,
    )


async def _process_media(
    state: AppState,
    enrollment_id: str,
    etype: str,
    files: list[UploadFile],
    *,
    default_source: str = "upload",
    sample_meta_json: str | None = None,
    video_modalities: str | None = None,
) -> tuple[QualityInfo, str | None]:
    from openrecognition.inference.audio_gate import AudioDecodeError

    dup_warning = None
    meta_list = parse_sample_meta_form(sample_meta_json, len(files))
    for i, f in enumerate(files):
        data = await f.read()
        kind = _detect_media_kind(data, f.content_type, f.filename)
        file_video_modalities = video_modalities
        if i < len(meta_list) and meta_list[i] is not None and meta_list[i].video_modalities:
            file_video_modalities = json.dumps(meta_list[i].video_modalities)

        if kind == "video":
            try:
                parts = process_video_enrollment(
                    state,
                    etype,
                    data,
                    video_modalities=file_video_modalities,
                )
            except VideoDecodeError as exc:
                name = f.filename or "upload"
                raise bad_request("INVALID_MEDIA", f"{name}: {exc}") from exc
            for part_idx, (part_data, part_kind, _, modality, ts) in enumerate(parts):
                try:
                    vec, mv, modality = _embed_sample(state, etype, part_data, part_kind)
                except AudioDecodeError as exc:
                    name = f.filename or "upload"
                    raise bad_request("INVALID_MEDIA", f"{name}: {exc}") from exc
                warn = state.gallery.find_duplicate_warning(vec, mv, exclude_id=enrollment_id)
                if warn and not dup_warning:
                    dup_warning = warn
                meta = _resolve_sample_meta(
                    f,
                    part_data,
                    part_kind,
                    i,
                    meta_list,
                    default_source=default_source,
                )
                if kind == "video":
                    meta.source = "video_clipper"
                if ts is not None:
                    meta.duration_ms = ts * 1000.0
                suffix = "wav" if part_kind == "audio" else "jpg"
                part_name = f"{Path(f.filename or 'clip').stem}-part{part_idx + 1}.{suffix}"
                meta.original_filename = part_name
                meta.content_type = (
                    "audio/wav" if part_kind == "audio" else "image/jpeg"
                )
                meta.size_bytes = len(part_data)
                emb_id = state.gallery.add_embedding(
                    enrollment_id, modality, vec, mv, meta=meta
                )
                if state.settings.enrollment_media_retention == "keep":
                    path = state.gallery.media_dir / f"{enrollment_id}_{uuid.uuid4().hex}"
                    path.write_bytes(part_data)
                    from openrecognition.gallery.store import _now as gallery_now

                    media_id = str(uuid.uuid4())
                    state.gallery.db.execute(
                        """INSERT INTO enrollment_media
                           (id, enrollment_id, path, modality, created_at, embedding_id)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            media_id,
                            enrollment_id,
                            str(path),
                            modality,
                            gallery_now(),
                            emb_id,
                        ),
                    )
            continue

        try:
            vec, mv, modality = _embed_sample(state, etype, data, kind)
        except AudioDecodeError as exc:
            name = f.filename or "upload"
            raise bad_request("INVALID_MEDIA", f"{name}: {exc}") from exc
        warn = state.gallery.find_duplicate_warning(vec, mv, exclude_id=enrollment_id)
        if warn and not dup_warning:
            dup_warning = warn
        meta = _resolve_sample_meta(
            f, data, kind, i, meta_list, default_source=default_source
        )
        emb_id = state.gallery.add_embedding(enrollment_id, modality, vec, mv, meta=meta)
        if state.settings.enrollment_media_retention == "keep":
            path = state.gallery.media_dir / f"{enrollment_id}_{uuid.uuid4().hex}"
            path.write_bytes(data)
            from openrecognition.gallery.store import _now as gallery_now

            media_id = str(uuid.uuid4())
            state.gallery.db.execute(
                """INSERT INTO enrollment_media
                   (id, enrollment_id, path, modality, created_at, embedding_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    media_id,
                    enrollment_id,
                    str(path),
                    modality,
                    gallery_now(),
                    emb_id,
                ),
            )
    quality = state.gallery.evaluate_enrollment(enrollment_id)
    return quality, dup_warning


@router.post("", response_model=EnrollmentOut)
async def create_enrollment(
    type: EnrollmentType = Form(...),
    label: str = Form(...),
    species_hint: str | None = Form(None),
    threshold: float | None = Form(None),
    enabled: str | None = Form(None),
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("enroll")),
    files: list[UploadFile] = File(default=[]),
    sample_meta: str | None = Form(None),
):
    if state.maintenance_mode:
        from openrecognition.api.errors import maintenance

        raise maintenance()
    en = state.gallery.create_enrollment(
        type,
        label,
        species_hint,
        threshold,
        _form_bool(enabled),
    )
    quality, dup = None, None
    if files:
        quality, dup = await _process_media(
            state,
            en["id"],
            type.value,
            files,
            default_source="enrollment_create",
            sample_meta_json=sample_meta,
        )
    en_out = state.gallery.get_enrollment(en["id"])
    summary = f"Created {type.value} enrollment"
    if files:
        summary += f" with {len(files)} sample(s)"
    _log_enrollment(state, "enrollment.created", en_out, auth=auth, summary=summary)
    return _to_out(en_out, quality, dup)


@router.get("", response_model=list[EnrollmentOut])
def list_enrollments(
    type: str | None = None,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    return [
        _to_out(e, state.gallery.evaluate_enrollment(e["id"]))
        for e in state.gallery.list_enrollments(type)
    ]


@router.get("/{enrollment_id}", response_model=EnrollmentOut)
def get_enrollment(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    en = state.gallery.get_enrollment(enrollment_id)
    if not en:
        raise not_found("Enrollment not found")
    return _to_out(en, state.gallery.evaluate_enrollment(enrollment_id))


@router.patch("/{enrollment_id}", response_model=EnrollmentOut)
def patch_enrollment(
    enrollment_id: str,
    body: EnrollmentPatch,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("enroll")),
):
    updates = body.model_dump(exclude_unset=True)
    if "label" in updates:
        label = str(updates.get("label") or "").strip()
        if not label:
            raise bad_request("INVALID_LABEL", "Name is required")
        updates["label"] = label
    en = state.gallery.patch_enrollment(enrollment_id, **updates)
    if not en:
        raise not_found("Enrollment not found")
    return _to_out(en, state.gallery.evaluate_enrollment(enrollment_id))


@router.delete("/{enrollment_id}", status_code=204)
def delete_enrollment(
    enrollment_id: str,
    purge_media: bool = False,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("enroll")),
):
    if not state.gallery.delete_enrollment(enrollment_id, purge_media=purge_media):
        raise not_found("Enrollment not found")


@router.get("/{enrollment_id}/samples", response_model=list[SampleOut])
def list_samples(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    if not state.gallery.get_enrollment(enrollment_id):
        raise not_found("Enrollment not found")
    return state.gallery.list_samples(enrollment_id)


@router.delete("/{enrollment_id}/samples/{sample_id}", status_code=204)
def delete_sample(
    enrollment_id: str,
    sample_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("enroll")),
):
    row = state.gallery.db.fetchone(
        "SELECT enrollment_id FROM embeddings WHERE id = ?",
        (sample_id,),
    )
    if not row or row["enrollment_id"] != enrollment_id:
        raise not_found("Sample not found")
    if not state.gallery.delete_sample(sample_id):
        raise not_found("Sample not found")


@router.post("/{enrollment_id}/samples", response_model=EnrollmentOut)
async def add_samples(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("enroll")),
    files: list[UploadFile] = File(...),
    sample_meta: str | None = Form(None),
    video_modalities: str | None = Form(None),
):
    en = state.gallery.get_enrollment(enrollment_id)
    if not en:
        raise not_found("Enrollment not found")
    quality, dup = await _process_media(
        state,
        enrollment_id,
        en["type"],
        files,
        default_source="upload",
        sample_meta_json=sample_meta,
        video_modalities=video_modalities,
    )
    en_out = state.gallery.get_enrollment(enrollment_id)
    _log_enrollment(
        state,
        "enrollment.samples_added",
        en_out,
        auth=auth,
        summary=f"Added {len(files)} sample(s)",
    )
    return _to_out(en_out, quality, dup)


@router.post("/{enrollment_id}/evaluate", response_model=QualityInfo)
def evaluate_enrollment(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    en = state.gallery.get_enrollment(enrollment_id)
    if not en:
        raise not_found("Enrollment not found")
    return state.gallery.evaluate_enrollment(enrollment_id)
