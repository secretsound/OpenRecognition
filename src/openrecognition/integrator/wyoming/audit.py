"""Write Wyoming Assist utterances to the recognition audit log."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("openrecognition.wyoming")

if TYPE_CHECKING:
    from openrecognition.integrator.recognition_log import RecognitionLogService
    from openrecognition.integrator.wyoming.processor import UtteranceResult


def _clip(text: str, limit: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _timing_summary(
    *,
    audio_sec: float,
    identify_ms: float,
    upstream_ms: float,
    total_ms: float,
    upstream_skipped: bool,
) -> str:
    parts = [
        f"audio {audio_sec:.2f}s",
        f"identify {identify_ms:.0f}ms",
    ]
    if upstream_skipped:
        parts.append("upstream skipped")
    else:
        parts.append(f"upstream {upstream_ms:.0f}ms")
    parts.append(f"total {total_ms:.0f}ms")
    return " · ".join(parts)


def _build_details(
    *,
    result: "UtteranceResult | None",
    text: str | None,
    audio_sec: float,
    identify_ms: float,
    upstream_ms: float,
    total_ms: float,
    upstream_skipped: bool,
    block_reason: str | None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "audio_sec": round(audio_sec, 2),
        "timing_ms": {
            "identify": round(identify_ms),
            "upstream": round(upstream_ms),
            "total": round(total_ms),
        },
        "upstream_skipped": upstream_skipped,
    }
    if text:
        details["transcript"] = text
    if block_reason:
        details["block_reason"] = block_reason
    if result is None:
        return details

    if result.gate_scores:
        details["gate_scores"] = {
            k: round(float(v), 4) for k, v in result.gate_scores.items()
        }
    if result.min_confidence is not None:
        details["min_confidence"] = result.min_confidence
    if getattr(result, "speaker_match_attempted", False) or result.candidates is not None:
        details["speaker_match_attempted"] = True
        details["gallery_count"] = getattr(result, "gallery_count", 0)
        details["comparable_speaker_count"] = getattr(result, "comparable_speaker_count", 0)
        if getattr(result, "speaker_model_version", None):
            details["speaker_model_version"] = result.speaker_model_version
        details["speaker_candidates"] = [
            {
                **row,
                "confidence": round(float(row["confidence"]), 4),
            }
            for row in (result.candidates or [])
        ]
    details["accepted"] = result.accepted
    return details


def log_wyoming_utterance(
    logs: "RecognitionLogService",
    *,
    event: str,
    result: "UtteranceResult | None" = None,
    text: str | None = None,
    audio_sec: float = 0.0,
    identify_ms: float = 0.0,
    upstream_ms: float = 0.0,
    total_ms: float = 0.0,
    upstream_skipped: bool = False,
    block_reason: str | None = None,
) -> None:
    """Persist a Wyoming pipeline result for Admin → Logs."""
    summary_parts: list[str] = []
    if text:
        summary_parts.append(f'"{_clip(text)}"')
    elif block_reason:
        summary_parts.append(block_reason)
    elif event == "wyoming.empty":
        summary_parts.append("No audio received")

    if event != "wyoming.empty":
        summary_parts.append(
            _timing_summary(
                audio_sec=audio_sec,
                identify_ms=identify_ms,
                upstream_ms=upstream_ms,
                total_ms=total_ms,
                upstream_skipped=upstream_skipped,
            )
        )

    details = _build_details(
        result=result,
        text=text,
        audio_sec=audio_sec,
        identify_ms=identify_ms,
        upstream_ms=upstream_ms,
        total_ms=total_ms,
        upstream_skipped=upstream_skipped,
        block_reason=block_reason,
    )

    try:
        logs.record(
            event=event,
            modality="audio",
            label=result.label if result else None,
            entity_id=result.enrollment_id if result else None,
            confidence=result.confidence if result else None,
            gate=result.gate if result else None,
            reason=result.reason if result else block_reason,
            summary=" · ".join(summary_parts) if summary_parts else None,
            latency_ms=total_ms if total_ms > 0 else None,
            actor_type="integration",
            actor_name="wyoming",
            details=details,
        )
    except Exception:
        logger.exception("Failed to write Wyoming utterance to recognition log")
