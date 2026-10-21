"""Tests for video demux helpers and capabilities limits."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from openrecognition.inference.video_demux import (
    VideoDecodeError,
    is_video_container,
    parse_video_modalities,
    probe_duration_sec,
    validate_video_clip,
)


def test_is_video_container_mp4_magic():
    data = b"\x00" * 4 + b"ftyp" + b"isom" + b"\x00" * 32
    assert is_video_container(data, "video/mp4", "clip.mp4")


def test_parse_video_modalities_defaults():
    assert parse_video_modalities(None) == {"face", "audio"}
    assert parse_video_modalities("both") == {"face", "audio"}
    assert parse_video_modalities('["face"]') == {"face"}
    assert parse_video_modalities('["audio"]') == {"audio"}


def test_capabilities_includes_video_limits(client, auth_headers):
    r = client.get("/v1/capabilities", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    limits = body.get("video_limits")
    assert limits is not None
    assert limits["enrollment_max_sec"] == 60
    assert limits["recognize_sync_max_sec"] == 120
    assert limits["recommended_sec"] == [10, 30]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_validate_and_probe_short_mp4():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.mp4"
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=2:size=160x120:rate=5",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(path),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            pytest.skip("ffmpeg could not synthesize test video")
        data = path.read_bytes()
    duration = probe_duration_sec(data)
    assert duration is not None
    assert 1.0 <= duration <= 3.5
    assert validate_video_clip(data, max_duration_sec=60, max_bytes=10_000_000) == duration


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_validate_rejects_long_clip():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "long.mp4"
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=5:size=160x120:rate=5",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(path),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            pytest.skip("ffmpeg could not synthesize test video")
        data = path.read_bytes()
    with pytest.raises(VideoDecodeError, match="maximum"):
        validate_video_clip(data, max_duration_sec=2, max_bytes=10_000_000)
