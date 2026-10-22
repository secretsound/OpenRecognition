"""Recognition endpoints."""

import time

import httpx
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel

from openrecognition.api.deps import get_request_id, get_state, require_scope
from openrecognition.api.errors import bad_request
from openrecognition.app_state import AppState
from openrecognition.inference.meta import inference_meta_kwargs
from openrecognition.inference.sound_events import classify_sound_events
from openrecognition.models.schemas import (
    CandidateMatch,
    EntityResult,
    MatchPolicy,
    MetaInfo,
    RecognizeDiagnostics,
    RecognizeResponse,
    RequestContext,
)
from openrecognition.outbound import UnsafeUrlError, fetch_bounded
from openrecognition.pipelines.video import recognize_video_bytes

router = APIRouter(prefix="/v1", tags=["recognize"])


def _min_confidence(state: AppState, value: float | None) -> float:
    return state.default_min_confidence if value is None else value


def _return_unknown(state: AppState, value: bool | None) -> bool:
    return state.default_return_unknown if value is None else value


def _include_sound_events(state: AppState, value: bool | None) -> bool:
    if value is not None:
        return value
    return state.default_include_sound_events


def _meta(state: AppState, **kwargs) -> MetaInfo:
    return MetaInfo(**kwargs, **inference_meta_kwargs(state))


class ImageUrlBody(BaseModel):
    url: str
    match_policy: MatchPolicy | None = None
    context: RequestContext | None = None


async def _dispatch(
    state: AppState,
    event: str,
    response: RecognizeResponse,
    dry_run: bool,
    auth: dict | None = None,
    extras: dict | None = None,
) -> None:
    """Webhooks, MQTT, presence — skipped when dry_run."""
    payload = response.model_dump()
    if extras:
        payload.update({k: v for k, v in extras.items() if v is not None})
    if not dry_run:
        await state.webhooks.dispatch_recognition(event, payload, dry_run=False)
        for ent in response.entities:
            if ent.entity_id and ent.label != "unknown":
                state.mqtt.publish_recognition(
                    ent.label,
                    ent.type,
                    {"confidence": ent.confidence, "modality": ent.modality},
                )
                state.gallery.update_presence(
                    ent.entity_id,
                    ent.label,
                    ent.type,
                    ent.modality,
                    response.meta.camera_id,
                    ent.confidence,
                )
    else:
        await state.webhooks.dispatch_recognition(event, payload, dry_run=True)


def _score_map(scores) -> dict[str, float] | None:
    if not scores:
        return None
    if hasattr(scores, "model_dump"):
        scores = scores.model_dump()
    return {key: round(float(value), 4) for key, value in scores.items() if value is not None}


def _speaker_log_details(
    candidates: list[dict] | None,
    *,
    min_confidence: float,
    scores,
    attempted: bool,
) -> dict:
    """Scores and the bar each enrollment actually had to clear."""
    rows = []
    for item in (candidates or [])[:8]:
        label = item.get("label")
        if not label or str(label).lower() == "unknown":
            continue
        row = {
            "label": label,
            "entity_id": item.get("entity_id"),
            "confidence": round(float(item.get("confidence") or 0.0), 4),
            "accepted": bool(item.get("accepted")),
        }
        used = item.get("threshold_used")
        if used is not None:
            row["threshold_used"] = round(float(used), 4)
        rows.append(row)
    details: dict = {
        "default_min_confidence": min_confidence,
        "min_confidence": min_confidence,
        "speaker_match_attempted": attempted or bool(rows),
        "speaker_candidates": rows,
    }
    mapped = _score_map(scores)
    if mapped:
        details["gate_scores"] = mapped
    return details


def _log_recognition(
    state: AppState,
    event: str,
    response: RecognizeResponse,
    *,
    dry_run: bool,
    auth: dict | None,
    modality: str | None = None,
    summary: str | None = None,
    details: dict | None = None,
) -> None:
    """Persist audit log entry (always, including sandbox / dry_run tests)."""
    meta = response.meta.model_dump()
    if response.entities:
        state.recognition_logs.append(
            event=event,
            response_meta=meta,
            entities=[e.model_dump() for e in response.entities],
            gate=response.gate,
            reason=response.reason,
            dry_run=dry_run,
            auth=auth,
            details=details,
        )
    else:
        state.recognition_logs.record(
            event=event,
            modality=modality,
            gate=response.gate,
            reason=response.reason,
            summary=summary,
            camera_id=meta.get("camera_id"),
            zone=meta.get("zone"),
            request_id=meta.get("request_id"),
            latency_ms=meta.get("latency_ms"),
            dry_run=dry_run,
            auth=auth,
            details=details,
        )


@router.post("/audio/gate")
async def audio_gate(
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("recognize")),
    file: UploadFile = File(...),
    request_id: str = Depends(get_request_id),
):
    data = await file.read()
    gate = state.gate.run(data)
    return gate


@router.post("/recognize/audio", response_model=RecognizeResponse)
async def recognize_audio(
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("recognize")),
    file: UploadFile = File(...),
    mode: str = Query("full", pattern="^(gate|identify|full)$"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    return_unknown: bool | None = Query(None),
    camera_id: str | None = None,
    zone: str | None = None,
    dry_run: bool = Query(False),
    include_sound_events: bool | None = Query(None),
    include_candidates: bool = Query(False),
    request_id: str = Depends(get_request_id),
):
    min_confidence = _min_confidence(state, min_confidence)
    return_unknown = _return_unknown(state, return_unknown)
    sound_events = _include_sound_events(state, include_sound_events)
    start = time.perf_counter()
    data = await file.read()
    gate = state.gate.run(data)
    entities: list[EntityResult] = []
    diagnostics: RecognizeDiagnostics | None = None
    if mode == "gate":
        lat = (time.perf_counter() - start) * 1000
        resp = RecognizeResponse(
            gate=gate.gate,
            reason=gate.reason,
            scores=gate.scores,
            meta=_meta(
                state,
                hardware=state.hardware_info()["effective"],
                latency_ms=lat,
                request_id=request_id,
                camera_id=camera_id,
                zone=zone,
                dry_run=dry_run,
            ),
        )
        _log_recognition(
            state,
            "recognition.gate",
            resp,
            dry_run=dry_run,
            auth=auth,
            modality="audio",
            summary=f"Gate-only check: {gate.gate}",
        )
        return resp
    ranked: list[dict] = []
    speaker_attempted = False
    if gate.gate == "accept" and mode in ("identify", "full"):
        speaker_block = state.inference_policy.identity_blocked("speaker_embedding")
        gallery = state.gallery.get_embeddings_for_match(modality="audio")
        if speaker_block:
            if include_candidates:
                diagnostics = RecognizeDiagnostics(
                    pipelines=["speaker"],
                    candidates=[],
                    notes=[speaker_block],
                )
        elif state.feature_flags.get("biometrics.speaker_enabled", True):
            from openrecognition.inference.alternates import speaker_alternates

            outcome = state.speaker.match_retained(
                data,
                gallery,
                min_confidence,
                return_unknown,
                alternates=speaker_alternates(state, gallery),
            )
            ranked = outcome["candidates"]
            speaker_attempted = True
            for m in outcome["matches"]:
                entities.append(EntityResult(**m))
            if (
                not dry_run
                and entities
                and entities[0].entity_id
                and entities[0].label != "unknown"
                and entities[0].modality == "audio"
                and outcome["model_version"] == state.speaker.current_model_version()
                and outcome["vector"] is not None
            ):
                from openrecognition.gallery.learn import maybe_learn_voice

                maybe_learn_voice(
                    state.gallery,
                    entities[0].entity_id,
                    outcome["vector"],
                    state.speaker.current_model_version(),
                    confidence=float(entities[0].confidence or 0.0),
                    candidates=ranked,
                    gate_accepted=True,
                    dry_run=False,
                )
            if include_candidates:
                notes = []
                if not gallery:
                    notes.append("Gallery is empty — enroll speakers first.")
                diagnostics = RecognizeDiagnostics(
                    pipelines=["speaker"],
                    candidates=[CandidateMatch(**c) for c in ranked],
                    notes=notes,
                )
        if sound_events:
            session = state.inference_policy.get_session("audio_gate_classifier")
            entities.extend(classify_sound_events(data, session=session))
    elif include_candidates and gate.gate != "accept":
        diagnostics = RecognizeDiagnostics(
            pipelines=[],
            candidates=[],
            notes=["Audio gate rejected this clip — speaker matching was skipped."],
        )
    lat = (time.perf_counter() - start) * 1000
    resp = RecognizeResponse(
        entities=entities,
        gate=gate.gate,
        reason=gate.reason,
        scores=gate.scores,
        diagnostics=diagnostics,
        meta=_meta(
            state,
            hardware=state.hardware_info()["effective"],
            latency_ms=lat,
            request_id=request_id,
            camera_id=camera_id,
            zone=zone,
            dry_run=dry_run,
        ),
    )
    log_details = _speaker_log_details(
        ranked,
        min_confidence=min_confidence,
        scores=gate.scores,
        attempted=speaker_attempted,
    )
    if gate.gate != "accept":
        _log_recognition(
            state,
            "recognition.gate_reject",
            resp,
            dry_run=dry_run,
            auth=auth,
            modality="audio",
            summary=gate.reason or "Audio gate rejected",
            details=log_details,
        )
        await _dispatch(
            state, "recognition.gate_reject", resp, dry_run, auth, extras={"mode": mode}
        )
    elif entities:
        event = "recognition.unknown" if entities[0].label == "unknown" else "recognition.match"
        _log_recognition(state, event, resp, dry_run=dry_run, auth=auth, details=log_details)
        await _dispatch(state, event, resp, dry_run, auth, extras={"mode": mode})
    else:
        _log_recognition(
            state,
            "recognition.no_match",
            resp,
            dry_run=dry_run,
            auth=auth,
            modality="audio",
            summary="No speaker matched the gallery",
            details=log_details,
        )
        await _dispatch(
            state, "recognition.no_match", resp, dry_run, auth, extras={"mode": mode}
        )
    return resp


async def _recognize_image_bytes(
    state: AppState,
    data: bytes,
    min_confidence: float,
    return_unknown: bool,
    camera_id: str | None,
    zone: str | None,
    dry_run: bool,
    request_id: str,
    auth: dict | None = None,
    *,
    include_candidates: bool = False,
) -> RecognizeResponse:
    start = time.perf_counter()
    from openrecognition.inference.alternates import face_alternates, visual_alternates

    gallery = state.gallery.get_embeddings_for_match(modality="image")
    face_block = state.inference_policy.identity_blocked("face_embedding")
    visual_block = state.inference_policy.identity_blocked("visual_reid")
    raw, diag_raw = state.vision.recognize_image(
        data,
        gallery,
        include_faces=state.feature_flags.get("biometrics.face_enabled", True) and not face_block,
        include_pets=state.feature_flags.get("biometrics.pet_enabled", True) and not visual_block,
        include_objects=not visual_block,
        min_confidence=min_confidence,
        return_unknown=return_unknown,
        include_candidates=include_candidates,
        face_alternates=face_alternates(state, gallery),
        visual_alternates=visual_alternates(state, gallery),
    )
    entities = [EntityResult(**e) for e in raw]
    diagnostics = None
    if diag_raw:
        diagnostics = RecognizeDiagnostics(
            pipelines=diag_raw["pipelines"],
            candidates=[CandidateMatch(**c) for c in diag_raw["candidates"]],
            notes=diag_raw["notes"],
        )
    blocked_notes = [note for note in (face_block, visual_block) if note]
    if blocked_notes:
        if diagnostics is None:
            diagnostics = RecognizeDiagnostics(notes=blocked_notes)
        else:
            diagnostics.notes.extend(blocked_notes)
    lat = (time.perf_counter() - start) * 1000
    resp = RecognizeResponse(
        entities=entities,
        diagnostics=diagnostics,
        meta=_meta(
            state,
            hardware=state.hardware_info()["effective"],
            latency_ms=lat,
            request_id=request_id,
            camera_id=camera_id,
            zone=zone,
            dry_run=dry_run,
        ),
    )
    if entities:
        event = "recognition.unknown" if entities[0].label == "unknown" else "recognition.match"
        _log_recognition(state, event, resp, dry_run=dry_run, auth=auth)
        await _dispatch(state, event, resp, dry_run, auth, extras={"mode": "image"})
    else:
        _log_recognition(
            state,
            "recognition.no_match",
            resp,
            dry_run=dry_run,
            auth=auth,
            modality="image",
            summary="No face/pet/object matched the gallery",
        )
        await _dispatch(
            state, "recognition.no_match", resp, dry_run, auth, extras={"mode": "image"}
        )
    return resp


@router.post("/recognize/image", response_model=RecognizeResponse)
async def recognize_image(
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("recognize")),
    file: UploadFile = File(...),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    return_unknown: bool | None = Query(None),
    camera_id: str | None = None,
    zone: str | None = None,
    dry_run: bool = Query(False),
    include_candidates: bool = Query(False),
    request_id: str = Depends(get_request_id),
):
    data = await file.read()
    return await _recognize_image_bytes(
        state,
        data,
        _min_confidence(state, min_confidence),
        _return_unknown(state, return_unknown),
        camera_id,
        zone,
        dry_run,
        request_id,
        auth,
        include_candidates=include_candidates,
    )


@router.post("/recognize/image/url", response_model=RecognizeResponse)
async def recognize_image_url(
    body: ImageUrlBody,
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("recognize")),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    return_unknown: bool | None = Query(None),
    dry_run: bool = Query(False),
    include_candidates: bool = Query(False),
    request_id: str = Depends(get_request_id),
):
    try:
        data = await fetch_bounded(body.url, max_bytes=20 * 1024 * 1024)
    except UnsafeUrlError as exc:
        raise bad_request("UNSAFE_URL", str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise bad_request(
            "FETCH_FAILED",
            f"Image URL returned HTTP {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise bad_request("FETCH_FAILED", "Could not fetch the image URL") from exc
    camera_id = body.context.camera_id if body.context else None
    zone = body.context.zone if body.context else None
    return await _recognize_image_bytes(
        state,
        data,
        _min_confidence(state, min_confidence),
        _return_unknown(state, return_unknown),
        camera_id,
        zone,
        dry_run,
        request_id,
        auth,
        include_candidates=include_candidates,
    )


@router.post("/recognize/video", response_model=RecognizeResponse)
async def recognize_video(
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("recognize")),
    file: UploadFile = File(...),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    return_unknown: bool | None = Query(None),
    dry_run: bool = Query(False),
    video_modalities: str | None = Query(None),
    include_candidates: bool = Query(False),
    request_id: str = Depends(get_request_id),
):
    """Process trimmed video clip: sample frames for vision + audio for speaker ID."""
    from openrecognition.inference.video_demux import VideoDecodeError

    min_confidence = _min_confidence(state, min_confidence)
    return_unknown = _return_unknown(state, return_unknown)
    start = time.perf_counter()
    data = await file.read()
    try:
        entities, gate_value, reason, scores, notes = recognize_video_bytes(
            state,
            data,
            min_confidence=min_confidence,
            return_unknown=return_unknown,
            video_modalities=video_modalities,
            dry_run=dry_run,
        )
    except VideoDecodeError as exc:
        from openrecognition.api.errors import bad_request

        raise bad_request("INVALID_MEDIA", str(exc)) from exc

    diagnostics = None
    if include_candidates or notes:
        diagnostics = RecognizeDiagnostics(
            pipelines=["video"],
            candidates=[],
            notes=notes,
        )

    lat = (time.perf_counter() - start) * 1000
    resp = RecognizeResponse(
        entities=entities,
        gate=gate_value,
        reason=reason,
        scores=scores,
        diagnostics=diagnostics,
        meta=_meta(
            state,
            hardware=state.hardware_info()["effective"],
            latency_ms=lat,
            request_id=request_id,
            dry_run=dry_run,
        ),
    )
    if entities:
        event = "recognition.unknown" if entities[0].label == "unknown" else "recognition.match"
        _log_recognition(state, event, resp, dry_run=dry_run, auth=auth)
        await _dispatch(state, event, resp, dry_run, auth, extras={"mode": "video"})
    else:
        _log_recognition(
            state,
            "recognition.no_match",
            resp,
            dry_run=dry_run,
            auth=auth,
            modality="video",
            summary="No match in video segment",
        )
        await _dispatch(
            state, "recognition.no_match", resp, dry_run, auth, extras={"mode": "video"}
        )
    return resp
