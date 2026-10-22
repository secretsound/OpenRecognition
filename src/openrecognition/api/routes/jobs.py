"""Async jobs for long video."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.errors import bad_request, not_found
from openrecognition.api.routes.recognize import (
    _dispatch,
    _log_recognition,
    _meta,
    _min_confidence,
    _return_unknown,
)
from openrecognition.app_state import AppState
from openrecognition.inference.video_demux import VideoDecodeError, validate_video_clip
from openrecognition.models.schemas import (
    EntityResult,
    JobOut,
    RecognizeDiagnostics,
    RecognizeResponse,
)
from openrecognition.pipelines.video import recognize_video_bytes

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _run_video_job(
    state: AppState,
    job_id: str,
    data: bytes,
    *,
    min_confidence: float,
    return_unknown: bool,
    dry_run: bool,
    video_modalities: str | None,
    include_candidates: bool,
    auth: dict | None,
) -> None:
    limits = state.video_limits()
    state.db.execute("UPDATE jobs SET status = ? WHERE id = ?", ("running", job_id))
    try:
        entities, gate, reason, scores, notes = recognize_video_bytes(
            state,
            data,
            min_confidence=min_confidence,
            return_unknown=return_unknown,
            video_modalities=video_modalities,
            dry_run=dry_run,
            max_duration_sec=float(limits["recognize_async_max_sec"]),
        )
        diagnostics = None
        if include_candidates or notes:
            diagnostics = RecognizeDiagnostics(
                pipelines=["video"],
                candidates=[],
                notes=notes,
            )
        result = RecognizeResponse(
            entities=[e if isinstance(e, EntityResult) else EntityResult(**e) for e in entities],
            gate=gate,
            reason=reason,
            scores=scores,
            diagnostics=diagnostics,
            meta=_meta(
                state,
                hardware=state.hardware_info()["effective"],
                latency_ms=0,
                request_id=job_id,
                dry_run=dry_run,
            ),
        )
        if notes and result.reason is None:
            result.reason = notes[0]
        if result.entities:
            event = (
                "recognition.unknown"
                if result.entities[0].label == "unknown"
                else "recognition.match"
            )
            _log_recognition(state, event, result, dry_run=dry_run, auth=auth)
            await _dispatch(state, event, result, dry_run, auth)
        else:
            _log_recognition(
                state,
                "recognition.no_match",
                result,
                dry_run=dry_run,
                auth=auth,
                modality="video",
                summary="No match in video segment",
            )
        state.db.execute(
            "UPDATE jobs SET status = ?, result = ?, completed_at = ? WHERE id = ?",
            ("completed", json.dumps(result.model_dump()), _now(), job_id),
        )
    except Exception as e:
        state.db.execute(
            "UPDATE jobs SET status = ?, error = ?, completed_at = ? WHERE id = ?",
            ("failed", str(e), _now(), job_id),
        )


@router.post("", response_model=JobOut, status_code=202)
async def create_job(
    background: BackgroundTasks,
    state: AppState = Depends(get_state),
    auth=Depends(require_scope("recognize")),
    file: UploadFile = File(...),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    return_unknown: bool | None = Query(None),
    dry_run: bool = Query(False),
    video_modalities: str | None = Query(None),
    include_candidates: bool = Query(False),
):
    job_id = str(uuid.uuid4())
    data = await file.read()
    limits = state.video_limits()
    try:
        validate_video_clip(
            data,
            max_duration_sec=float(limits["recognize_async_max_sec"]),
            max_bytes=int(limits["max_upload_bytes"]),
        )
    except VideoDecodeError as exc:
        raise bad_request("INVALID_MEDIA", str(exc)) from exc
    options = {
        "min_confidence": _min_confidence(state, min_confidence),
        "return_unknown": _return_unknown(state, return_unknown),
        "dry_run": dry_run,
        "video_modalities": video_modalities,
        "include_candidates": include_candidates,
    }
    state.db.execute(
        """INSERT INTO jobs (id, status, job_type, payload, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (job_id, "pending", "video", json.dumps(options), _now()),
    )
    background.add_task(
        _run_video_job,
        state,
        job_id,
        data,
        min_confidence=options["min_confidence"],
        return_unknown=options["return_unknown"],
        dry_run=dry_run,
        video_modalities=video_modalities,
        include_candidates=include_candidates,
        auth=auth,
    )
    return JobOut(id=job_id, status="pending", created_at=_now())


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    state: AppState = Depends(get_state),
    _auth=Depends(require_scope("read")),
):
    row = state.db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if not row:
        raise not_found("Job not found")
    result = None
    if row["result"]:
        result = RecognizeResponse(**json.loads(row["result"]))
    return JobOut(
        id=row["id"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        result=result,
        error=row["error"],
    )
