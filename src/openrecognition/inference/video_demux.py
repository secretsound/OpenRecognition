"""Video demux: duration checks, frame sampling, audio extraction via ffmpeg."""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image

VideoModality = Literal["face", "audio", "visual"]

_VIDEO_TYPES = frozenset(
    {
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-matroska",
        "video/ogg",
        "video/x-msvideo",
    }
)
_VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v", ".ogv")


class VideoDecodeError(ValueError):
    """Video bytes could not be demuxed."""


@dataclass(frozen=True)
class VideoFrame:
    timestamp_sec: float
    jpeg_bytes: bytes


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def is_video_container(
    data: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> bool:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in _VIDEO_TYPES:
        return True
    name = (filename or "").lower()
    if name.endswith(_VIDEO_EXTENSIONS):
        return True
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return True
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return True
    return False


def _write_temp_video(data: bytes, suffix: str = ".mp4") -> Path:
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with open(fd, "wb") as f:
            f.write(data)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)


def probe_duration_sec(data: bytes) -> float | None:
    if not ffprobe_available():
        return None
    path = _write_temp_video(data)
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        return float(proc.stdout.decode().strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    finally:
        path.unlink(missing_ok=True)


def probe_has_video_stream(data: bytes) -> bool:
    if not ffprobe_available():
        return True
    path = _write_temp_video(data)
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            return False
        return proc.stdout.decode().strip().lower() == "video"
    except (OSError, subprocess.TimeoutExpired):
        return True
    finally:
        path.unlink(missing_ok=True)


def validate_video_clip(
    data: bytes,
    *,
    max_duration_sec: float,
    max_bytes: int,
) -> float:
    if len(data) > max_bytes:
        raise VideoDecodeError(
            f"Video clip exceeds maximum size ({len(data)} > {max_bytes} bytes)."
        )
    duration = probe_duration_sec(data)
    if duration is None:
        raise VideoDecodeError(
            "Could not read video duration. Install ffmpeg/ffprobe on the server "
            "or upload a shorter clip exported from the browser trimmer."
        )
    if duration <= 0:
        raise VideoDecodeError("Video clip has zero duration.")
    if duration > max_duration_sec:
        raise VideoDecodeError(
            f"Video clip is {duration:.1f}s — maximum allowed is {max_duration_sec:.0f}s. "
            "Trim a shorter segment before uploading."
        )
    return duration


def extract_audio_wav(data: bytes, *, timeout: int = 120) -> bytes:
    if not ffmpeg_available():
        raise VideoDecodeError(
            "ffmpeg is required to extract audio from video. "
            "Install ffmpeg on the server (e.g. apt install ffmpeg)."
        )
    path = _write_temp_video(data)
    out_path = path.with_suffix(".wav")
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(out_path),
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0 or not out_path.is_file():
            err = (proc.stderr or b"").decode(errors="replace").strip()
            raise VideoDecodeError(
                f"Could not extract audio from video.{f' {err}' if err else ''}"
            )
        return out_path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


def sample_frames(
    data: bytes,
    *,
    fps: float = 3.0,
    max_frames: int = 24,
    timeout: int = 120,
) -> list[VideoFrame]:
    if not ffmpeg_available():
        raise VideoDecodeError(
            "ffmpeg is required to sample video frames. "
            "Install ffmpeg on the server (e.g. apt install ffmpeg)."
        )
    duration = probe_duration_sec(data)
    if duration is None or duration <= 0:
        raise VideoDecodeError("Could not determine video duration for frame sampling.")

    interval = 1.0 / max(fps, 0.5)
    timestamps: list[float] = []
    t = 0.0
    while t < duration and len(timestamps) < max_frames:
        timestamps.append(t)
        t += interval

    path = _write_temp_video(data)
    frames: list[VideoFrame] = []
    try:
        for ts in timestamps:
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{ts:.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "mjpeg",
                    "pipe:1",
                ],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout:
                continue
            jpeg = proc.stdout
            try:
                Image.open(io.BytesIO(jpeg)).verify()
            except Exception:
                continue
            frames.append(VideoFrame(timestamp_sec=ts, jpeg_bytes=jpeg))
    finally:
        path.unlink(missing_ok=True)

    if not frames:
        if not probe_has_video_stream(data):
            raise VideoDecodeError(
                "This clip has no decodable video track (audio-only). "
                "Re-extract with a browser-compatible H.264/VP8 source, or use Voice only."
            )
        raise VideoDecodeError("No frames could be extracted from the video clip.")
    return frames


def parse_video_modalities(raw: str | None) -> set[str]:
    if not raw or not raw.strip():
        return {"face", "audio"}
    import json

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
        if parts == {"both"} or parts == {"all"}:
            return {"face", "audio"}
        return parts or {"face", "audio"}
    if isinstance(payload, str):
        p = payload.strip().lower()
        if p in ("both", "all"):
            return {"face", "audio"}
        return {p} if p else {"face", "audio"}
    if isinstance(payload, list):
        mods = {str(x).strip().lower() for x in payload}
        if "both" in mods or "all" in mods:
            return {"face", "audio"}
        out: set[str] = set()
        for m in mods:
            if m in ("face", "visual", "audio", "voice"):
                out.add("audio" if m in ("audio", "voice") else m)
        return out or {"face", "audio"}
    return {"face", "audio"}
