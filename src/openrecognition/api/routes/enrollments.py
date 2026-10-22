"""Enrollment CRUD."""

import io
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile  # noqa: F401
from PIL import Image, UnidentifiedImageError

from openrecognition.api.deps import (
    get_auth,
    get_request_id,
    get_state,
    can_delete_enrollment,
    library_limited_ids,
    require_enrollment_right,
    require_enrollment_view,
    require_scope,
)
from openrecognition.api.errors import bad_request, forbidden, not_found, unauthorized
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
    SamplePreviewOut,
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
        return state.speaker.embed(data, stabilize=True), state.speaker.model_version, "audio"
    # person: voice and/or face
    if kind == "audio":
        return state.speaker.embed(data, stabilize=True), state.speaker.model_version, "audio"
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


def _to_out(
    en: dict,
    quality: QualityInfo | None = None,
    dup: str | None = None,
    last_seen: str | None = None,
) -> EnrollmentOut:
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
        wyoming_min_confidence=en.get("wyoming_min_confidence"),
        external_ids=en.get("external_ids") or {},
        sample_count=en["sample_count"],
        model_version=en.get("model_version"),
        created_at=en["created_at"],
        updated_at=en["updated_at"],
        quality=quality,
        duplicate_warning=dup,
        last_seen_at=last_seen,
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
        created_by=auth.get("user_id") if auth else None,
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
    else:
        quality = state.gallery.evaluate_enrollment(en["id"])
    en_out = state.gallery.get_enrollment(en["id"])
    summary = f"Created {type.value} enrollment"
    if files:
        summary += f" with {len(files)} sample(s)"
    _log_enrollment(state, "enrollment.created", en_out, auth=auth, summary=summary)
    return _to_out(en_out, quality, dup)


@router.get("", response_model=list[EnrollmentOut])
def list_enrollments(
    type: str | None = Query(None, description="Filter by enrollment type"),
    q: str | None = Query(None, description="Case-insensitive name search"),
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("read")),
):
    rows = state.gallery.list_enrollments(type, q=q)
    allowed = library_limited_ids(state, auth)
    if allowed is not None:
        rows = [e for e in rows if e["id"] in allowed]
    quality = state.gallery.evaluate_many(rows)
    seen = state.gallery.presence_map()
    return [_to_out(e, quality.get(e["id"]), last_seen=seen.get(e["id"])) for e in rows]


@router.get("/{enrollment_id}", response_model=EnrollmentOut)
def get_enrollment(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("read")),
):
    require_enrollment_view(state, auth, enrollment_id)
    en = state.gallery.get_enrollment(enrollment_id)
    if not en:
        raise not_found("Enrollment not found")
    return _to_out(
        en,
        state.gallery.evaluate_enrollment(enrollment_id),
        last_seen=state.gallery.last_seen_at(enrollment_id),
    )


@router.patch("/{enrollment_id}", response_model=EnrollmentOut)
def patch_enrollment(
    enrollment_id: str,
    body: EnrollmentPatch,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
):
    require_enrollment_right(state, auth, enrollment_id, "manage")
    updates = body.model_dump(exclude_unset=True)
    if "label" in updates:
        label = str(updates.get("label") or "").strip()
        if not label:
            raise bad_request("INVALID_LABEL", "Name is required")
        updates["label"] = label
    en = state.gallery.patch_enrollment(enrollment_id, **updates)
    if not en:
        raise not_found("Enrollment not found")
    return _to_out(
        en,
        state.gallery.evaluate_enrollment(enrollment_id),
        last_seen=state.gallery.last_seen_at(enrollment_id),
    )


@router.delete("/{enrollment_id}", status_code=204)
def delete_enrollment(
    enrollment_id: str,
    purge_media: bool = False,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
):
    if not auth:
        raise unauthorized()
    scopes = auth.get("scopes") or []
    if auth.get("user_id"):
        if "admin" not in scopes and "enroll" not in scopes:
            raise forbidden("Scope 'enroll' required")
    elif "admin" not in scopes and "delete" not in scopes:
        raise forbidden("Scope 'delete' required")
    require_enrollment_view(state, auth, enrollment_id)
    if not can_delete_enrollment(state, auth, enrollment_id):
        raise forbidden("You can only delete enrollments you created")
    if not state.gallery.delete_enrollment(enrollment_id, purge_media=purge_media):
        raise not_found("Enrollment not found")


@router.get("/{enrollment_id}/samples", response_model=list[SampleOut])
def list_samples(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("read")),
):
    require_enrollment_view(state, auth, enrollment_id)
    if not state.gallery.get_enrollment(enrollment_id):
        raise not_found("Enrollment not found")
    return state.gallery.list_samples(enrollment_id)


@router.delete("/{enrollment_id}/samples/{sample_id}", status_code=204)
def delete_sample(
    enrollment_id: str,
    sample_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
):
    require_enrollment_right(state, auth, enrollment_id, "manage")
    row = state.gallery.db.fetchone(
        "SELECT enrollment_id FROM embeddings WHERE id = ?",
        (sample_id,),
    )
    if not row or row["enrollment_id"] != enrollment_id:
        raise not_found("Sample not found")
    if not state.gallery.delete_sample(sample_id):
        raise not_found("Sample not found")


def _duration_score(duration_ms: float | None) -> float:
    if duration_ms is None:
        return 0.5
    if duration_ms < 1500:
        return 0.15
    if duration_ms < 2500:
        return 0.35
    if duration_ms < 4000:
        return 0.7
    if duration_ms <= 8000:
        return 1.0
    if duration_ms <= 12000:
        return 0.9
    return 0.75


def _preview_advice(issues: list[str], *, has_fit: bool, kind: str = "audio") -> str:
    if "silence" in issues:
        return "Almost no voice was heard. Move closer or speak louder."
    if "too_short" in issues:
        return "Finish the whole sentence — four to six seconds works best."
    if "music" in issues:
        return "This sounds like music, not speech. Try again in a quiet room."
    if "background_noise" in issues:
        return "Too much background noise. Try a quieter room and re-record."
    if "no_face" in issues:
        return "No face was found. Look at the camera and fit your face in the oval."
    if "face_too_small" in issues:
        return "Move closer so your face fills more of the frame."
    if "too_dark" in issues:
        return "This is too dark. Face a window or lamp — don't stand with bright light behind you."
    if "too_bright" in issues:
        return "This is washed out. Turn so the light is not shining straight into the lens."
    if "blurry" in issues:
        return "This is soft. Hold still and try again."
    if "multiple_faces" in issues:
        return "More than one face is in the shot. Get the others out of frame."
    if "poor_fit" in issues:
        if kind == "image":
            return "This photo does not match the face you already taught. Make sure it is the same person."
        return "This take does not match your other voice samples. Make sure it is the same person."
    if "low_fit" in issues:
        if kind == "image":
            return "This photo is a bit different from your other shots. Retake if it is not the same person."
        return "This take is a bit different from your other samples. Re-record if someone else was talking."
    if "a_bit_short" in issues:
        return "A little short. Re-record if you cut off the last words."
    if has_fit:
        return "This take looks good and matches what you already taught."
    return "This take looks good."


def _preview_audio(
    state: AppState,
    enrollment_id: str,
    etype: str,
    data: bytes,
) -> SamplePreviewOut:
    duration_ms = _audio_duration_ms(data)
    gate = state.gate.run(data)
    speech = (gate.scores or {}).get("speech")
    issues: list[str] = []

    if duration_ms is not None and duration_ms < 2500:
        issues.append("too_short")
    elif duration_ms is not None and duration_ms < 4000:
        issues.append("a_bit_short")

    if gate.gate == "reject" and gate.reason:
        if gate.reason not in issues:
            issues.append(gate.reason)

    sim: float | None = None
    try:
        vec, model_version, _ = _embed_sample(state, etype, data, "audio")
        raw = state.gallery.similarity_to_centroid(enrollment_id, vec, model_version)
        if raw is not None:
            sim = float(raw)
            if sim < 0.35:
                issues.append("poor_fit")
            elif sim < 0.5:
                issues.append("low_fit")
    except Exception:
        sim = None

    speech_score = float(speech) if speech is not None else 0.5
    if gate.gate == "reject":
        speech_score = min(speech_score, 0.25)
    duration_score = _duration_score(duration_ms)
    if sim is None:
        score = 0.45 * duration_score + 0.55 * speech_score
    else:
        score = 0.3 * duration_score + 0.35 * speech_score + 0.35 * sim
    score = max(0.0, min(1.0, score))

    hard = {"too_short", "silence", "poor_fit", "music"}
    verdict = "retry" if score < 0.55 or any(i in hard for i in issues) else "keep"

    return SamplePreviewOut(
        score=round(score, 3),
        verdict=verdict,
        duration_ms=duration_ms,
        gate=gate.gate,
        reason=gate.reason,
        speech=round(speech_score, 3),
        centroid_similarity=round(sim, 4) if sim is not None else None,
        issues=issues,
        advice=_preview_advice(issues, has_fit=sim is not None, kind="audio"),
    )


def _preview_image(
    state: AppState,
    enrollment_id: str,
    etype: str,
    data: bytes,
) -> SamplePreviewOut:
    info = state.vision.inspect_image(data)
    issues: list[str] = []
    brightness = float(info.get("brightness") or 0)
    sharpness = float(info.get("sharpness") or 0)
    if brightness < 0.18:
        issues.append("too_dark")
    elif brightness > 0.9:
        issues.append("too_bright")
    if sharpness < 0.02:
        issues.append("blurry")

    if etype == "person" and info.get("detector"):
        count = int(info.get("face_count") or 0)
        frac = float(info.get("face_frac") or 0)
        if count == 0:
            issues.append("no_face")
        elif count > 1:
            issues.append("multiple_faces")
        if count >= 1 and frac < 0.08:
            issues.append("face_too_small")

    sim: float | None = None
    try:
        vec, model_version, _ = _embed_sample(state, etype, data, "image")
        raw = state.gallery.similarity_to_centroid(enrollment_id, vec, model_version)
        if raw is not None:
            sim = float(raw)
            if sim < 0.35:
                issues.append("poor_fit")
            elif sim < 0.5:
                issues.append("low_fit")
    except Exception:
        sim = None

    light_score = 0.25 if ("too_dark" in issues or "too_bright" in issues) else 1.0
    sharp_score = max(0.0, min(1.0, sharpness / 0.05))
    face_score = 0.2 if "no_face" in issues else 1.0
    if sim is None:
        score = 0.35 * light_score + 0.35 * sharp_score + 0.3 * face_score
    else:
        score = 0.25 * light_score + 0.25 * sharp_score + 0.2 * face_score + 0.3 * sim
    score = max(0.0, min(1.0, score))
    hard = {"too_dark", "blurry", "no_face", "poor_fit"}
    verdict = "retry" if score < 0.55 or any(i in hard for i in issues) else "keep"
    return SamplePreviewOut(
        score=round(score, 3),
        verdict=verdict,
        duration_ms=None,
        gate=None,
        reason=issues[0] if issues else None,
        speech=None,
        centroid_similarity=round(sim, 4) if sim is not None else None,
        issues=issues,
        advice=_preview_advice(issues, has_fit=sim is not None, kind="image"),
    )


@router.post("/{enrollment_id}/samples/preview", response_model=SamplePreviewOut)
async def preview_sample(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
    file: UploadFile = File(...),
):
    require_enrollment_right(state, auth, enrollment_id, "add_samples")
    en = state.gallery.get_enrollment(enrollment_id)
    if not en:
        raise not_found("Enrollment not found")
    data = await file.read()
    if not data:
        raise bad_request("INVALID_MEDIA", "Empty file")
    kind = _detect_media_kind(data, file.content_type, file.filename)
    if kind == "audio":
        return _preview_audio(state, enrollment_id, en["type"], data)
    if kind == "image":
        return _preview_image(state, enrollment_id, en["type"], data)
    raise bad_request("INVALID_MEDIA", "Preview supports audio or photo takes.")


@router.post("/{enrollment_id}/samples", response_model=EnrollmentOut)
async def add_samples(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(get_auth),
    files: list[UploadFile] = File(...),
    sample_meta: str | None = Form(None),
    video_modalities: str | None = Form(None),
):
    require_enrollment_right(state, auth, enrollment_id, "add_samples")
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
    return _to_out(
        en_out,
        quality,
        dup,
        last_seen=state.gallery.last_seen_at(enrollment_id),
    )


@router.post("/{enrollment_id}/evaluate", response_model=QualityInfo)
def evaluate_enrollment(
    enrollment_id: str,
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("read")),
):
    require_enrollment_view(state, auth, enrollment_id)
    en = state.gallery.get_enrollment(enrollment_id)
    if not en:
        raise not_found("Enrollment not found")
    return state.gallery.evaluate_enrollment(enrollment_id)
