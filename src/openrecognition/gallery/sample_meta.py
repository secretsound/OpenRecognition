"""Sample metadata for enrollment embeddings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_VOICE_PHRASE_RE = re.compile(r"voice-phrase-(\d+)\.wav$", re.I)


@dataclass
class SampleMeta:
    source: str = "upload"
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    duration_ms: float | None = None
    phrase_index: int | None = None
    phrase_text: str | None = None
    video_modalities: list[str] | None = None

    @classmethod
    def from_upload(
        cls,
        *,
        filename: str | None,
        content_type: str | None,
        size_bytes: int,
        duration_ms: float | None = None,
        source: str = "upload",
    ) -> SampleMeta:
        meta = cls(
            source=source,
            original_filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            duration_ms=duration_ms,
        )
        if filename:
            m = _VOICE_PHRASE_RE.search(filename)
            if m:
                meta.source = "voice_wizard"
                meta.phrase_index = int(m.group(1)) - 1
        return meta

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SampleMeta:
        mods = data.get("video_modalities")
        if isinstance(mods, list):
            video_modalities = [str(m) for m in mods]
        else:
            video_modalities = None
        return cls(
            source=str(data.get("source") or "upload"),
            original_filename=data.get("original_filename"),
            content_type=data.get("content_type"),
            size_bytes=data.get("size_bytes"),
            duration_ms=data.get("duration_ms"),
            phrase_index=data.get("phrase_index"),
            phrase_text=data.get("phrase_text"),
            video_modalities=video_modalities,
        )


def parse_sample_meta_form(raw: str | None, file_count: int) -> list[SampleMeta | None]:
    if not raw or not raw.strip():
        return [None] * file_count
    import json

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return [None] * file_count
    if not isinstance(payload, list):
        return [None] * file_count
    out: list[SampleMeta | None] = []
    for i in range(file_count):
        if i < len(payload) and isinstance(payload[i], dict):
            out.append(SampleMeta.from_dict(payload[i]))
        else:
            out.append(None)
    return out


def source_display(meta: SampleMeta) -> str:
    if meta.source == "voice_wizard":
        if meta.phrase_index is not None:
            n = meta.phrase_index + 1
            if meta.phrase_text:
                short = meta.phrase_text[:48] + ("…" if len(meta.phrase_text) > 48 else "")
                return f"Guided phrase {n}: {short}"
            return f"Guided phrase {n}"
        return "Guided enrollment"
    if meta.source == "video_clipper":
        return "Video clip"
    if meta.source == "enrollment_create":
        return "Initial enrollment"
    if meta.source == "match_learn":
        if meta.phrase_text:
            return meta.phrase_text
        return "Learned from a match"
    if meta.original_filename:
        return f"Upload: {meta.original_filename}"
    return "File upload"
