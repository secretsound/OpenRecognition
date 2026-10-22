"""Self-host settings: time zone, limits, monitors, backup, and disk use."""

import io
import json
import zipfile


def _restore(client, auth_headers, payload: bytes):
    return client.post(
        "/v1/admin/backup/restore",
        headers=auth_headers,
        files={"file": ("openrecognition-backup.zip", payload, "application/zip")},
        data={"confirm": "restore"},
    )


def test_hosting_limits_timezone_and_monitors(client, auth_headers):
    before = client.get("/v1/admin/settings", headers=auth_headers).json()
    try:
        saved = client.patch(
            "/v1/admin/settings",
            headers=auth_headers,
            json={
                "display_timezone": "America/Los_Angeles",
                "auth_rate_limit_per_minute": 12,
                "video_max_upload_bytes": 20 * 1024 * 1024,
                "log_max_mb": 8,
                "log_backup_count": 3,
                "health_detail_public": False,
                "metrics_token": "metrics-token-value1",
            },
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["display_timezone"] == "America/Los_Angeles"
        assert body["auth_rate_limit_per_minute"] == 12
        assert body["video_max_upload_bytes"] == 20 * 1024 * 1024
        assert body["log_max_mb"] == 8
        assert body["log_backup_count"] == 3
        assert body["health_detail_public"] is False
        assert body["metrics_token_set"] is True
        assert "metrics_token" not in body

        ui = client.get("/v1/auth/ui")
        assert ui.status_code == 200
        assert ui.json()["display_timezone"] == "America/Los_Angeles"

        assert client.get("/health").status_code == 401
        assert client.get("/health", headers=auth_headers).status_code == 200
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/metrics").status_code == 401
        metrics = client.get("/metrics", headers={"Authorization": "Bearer metrics-token-value1"})
        assert metrics.status_code == 200
        assert "openrecognition_info" in metrics.text
        assert client.get("/metrics", headers=auth_headers).status_code == 200

        usage = client.get("/v1/admin/storage-usage", headers=auth_headers)
        assert usage.status_code == 200
        sizes = usage.json()
        assert sizes["data_bytes"] >= 0
        assert sizes["models_bytes"] >= 0
        assert sizes["logs_bytes"] >= 0

        rejected = client.patch(
            "/v1/admin/settings",
            headers=auth_headers,
            json={"display_timezone": "Not/AZone"},
        )
        assert rejected.status_code == 400
    finally:
        client.patch(
            "/v1/admin/settings",
            headers=auth_headers,
            json={
                "display_timezone": before.get("display_timezone") or "UTC",
                "auth_rate_limit_per_minute": before["auth_rate_limit_per_minute"],
                "video_max_upload_bytes": before.get("video_max_upload_bytes") or 100 * 1024 * 1024,
                "log_max_mb": before.get("log_max_mb") or 5,
                "log_backup_count": before.get("log_backup_count") or 5,
                "health_detail_public": True,
                "clear_metrics_token": True,
            },
        )


def test_backup_restore_roundtrip(client, auth_headers):
    original = client.get("/v1/admin/backup", headers=auth_headers)
    assert original.status_code == 200
    assert "zip" in original.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(original.content)) as archive:
        names = set(archive.namelist())
        database = archive.read("openrecognition.db")
        settings = json.loads(archive.read("runtime_settings.json"))
    assert {"openrecognition.db", "runtime_settings.json", "manifest.json"} <= names

    junk = _restore(client, auth_headers, b"not a zip")
    assert junk.status_code == 400

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("openrecognition.db", database)
        archive.writestr("notes.txt", "nope")
    rejected = _restore(client, auth_headers, payload.getvalue())
    assert rejected.status_code == 400

    settings["display_timezone"] = "Pacific/Auckland"
    updated = io.BytesIO()
    with zipfile.ZipFile(updated, "w") as archive:
        archive.writestr("openrecognition.db", database)
        archive.writestr("runtime_settings.json", json.dumps(settings))
    try:
        restored = _restore(client, auth_headers, updated.getvalue())
        assert restored.status_code == 200, restored.text
        body = client.get("/v1/admin/settings", headers=auth_headers).json()
        assert body["display_timezone"] == "Pacific/Auckland"
        still = client.get("/v1/auth/me", headers=auth_headers)
        assert still.status_code == 200
    finally:
        put_back = _restore(client, auth_headers, original.content)
        assert put_back.status_code == 200, put_back.text
