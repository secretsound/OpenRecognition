"""Async video jobs run the video pipeline."""

from openrecognition.models.schemas import EntityResult


def test_video_job_rejects_oversized_upload(client, auth_headers):
    state = client.app.state.app_state
    previous = state.settings.video_max_upload_bytes
    state.settings.video_max_upload_bytes = 8
    try:
        response = client.post(
            "/v1/jobs",
            headers=auth_headers,
            files={"file": ("clip.mp4", b"0123456789", "video/mp4")},
        )
    finally:
        state.settings.video_max_upload_bytes = previous
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_MEDIA"


def test_video_job_runs_video_pipeline(client, auth_headers, monkeypatch):
    state = client.app.state.app_state
    seen: dict = {}

    def fake_validate(data, *, max_duration_sec, max_bytes):
        seen["validate"] = {
            "size": len(data),
            "max_duration_sec": max_duration_sec,
            "max_bytes": max_bytes,
        }
        return 1.5

    def fake_recognize(app_state, data, **kwargs):
        row = app_state.db.fetchone(
            "SELECT status FROM jobs ORDER BY created_at DESC LIMIT 1"
        )
        seen["status_during"] = row["status"]
        seen["kwargs"] = kwargs
        seen["nbytes"] = len(data)
        return (
            [
                EntityResult(
                    label="Luke",
                    type="person",
                    recognition_type="face",
                    confidence=0.91,
                    modality="image",
                )
            ],
            None,
            None,
            None,
            [],
        )

    monkeypatch.setattr(
        "openrecognition.api.routes.jobs.validate_video_clip", fake_validate
    )
    monkeypatch.setattr(
        "openrecognition.api.routes.jobs.recognize_video_bytes", fake_recognize
    )

    payload = b"not-a-real-mp4"
    response = client.post(
        "/v1/jobs",
        headers=auth_headers,
        files={"file": ("clip.mp4", payload, "video/mp4")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert seen["validate"]["max_duration_sec"] == state.settings.video_recognize_async_max_sec
    assert seen["validate"]["max_bytes"] == state.settings.video_max_upload_bytes
    assert seen["status_during"] == "running"
    assert seen["kwargs"]["max_duration_sec"] == state.settings.video_recognize_async_max_sec
    assert seen["kwargs"]["min_confidence"] == state.default_min_confidence
    assert seen["nbytes"] == len(payload)

    fetched = client.get(f"/v1/jobs/{body['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    done = fetched.json()
    assert done["status"] == "completed"
    assert done["result"]["entities"][0]["label"] == "Luke"
    assert done["result"]["entities"][0]["recognition_type"] == "face"
