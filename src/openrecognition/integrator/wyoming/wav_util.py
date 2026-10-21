"""PCM buffer to WAV bytes for in-process gate/speaker pipelines."""

from __future__ import annotations

import io
import wave


def pcm_to_wav(
    pcm: bytes,
    rate: int,
    width: int = 2,
    channels: int = 1,
) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()
