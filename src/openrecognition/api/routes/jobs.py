"""Async jobs for long video."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from openrecognition.api.deps import get_state, require_scope
from openrecognition.api.errors import bad_request, not_found
from openrecognition.app_state import AppState
from openrecognition.inference.video_demux import VideoDecodeError, validate_video_clip
from openrecognition.models.schemas import EntityResult, JobOut, MetaInfo, RecognizeResponse
from openrecognition.pipelines.video import recognize_video_bytes

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_video_job(state: AppState, job_id: str, data: bytes) -> None:
    limits = state.video_limits()
    state.db.execute("UPDATE jobs SET status = ? WHERE id = ?", ("running", job_id))
    try:
        entities, gate, reason, scores, notes = recognize_video_bytes(
            state,
            data,
            min_confidence=state.default_min_confidence,
            return_unknown=state.default_return_unknown,
            max_duration_sec=float(limits["recognize_async_max_sec"]),
        )
        result = RecognizeResponse(
            entities=[e if isinstance(e, EntityResult) else EntityResult(**e) for e in entities],
            gate=gate,
            reason=reason,
            scores=scores,
            meta=MetaInfo(
                pack=state.settings.pack,
                latency_ms=0,
                request_id=job_id,
            ),
        )
        if notes and result.reason is None:
            result.reason = notes[0]
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
    _auth=Depends(require_scope("recognize")),
    file: UploadFile = File(...),
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
    state.db.execute(
        """INSERT INTO jobs (id, status, job_type, payload, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (job_id, "pending", "video", "{}", _now()),
    )
    background.add_task(_run_video_job, state, job_id, data)
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
