"""Tell Home Assistant who spoke and what the gate decided.

Home Assistant's built-in Wyoming speech-to-text entity keeps only the transcript
text. ``context.speaker`` is on that same packet so the OpenRecognition
integration can pass the person to the next conversation. The recognition
webhook still updates the last-speaker sensor and the recognition event.
"""

from __future__ import annotations

import logging
from typing import Any

from openrecognition.integrator.wyoming.processor import UtteranceResult

logger = logging.getLogger(__name__)


def person_entity_id(state: Any, enrollment_id: str | None) -> str | None:
    """Return the Home Assistant person id stored on the enrollment, if any."""
    if not enrollment_id:
        return None
    gallery = getattr(state, "gallery", None)
    getter = getattr(gallery, "get_enrollment", None)
    if not callable(getter):
        return None
    try:
        enrollment = getter(enrollment_id)
    except Exception:
        logger.debug("Could not load enrollment %s for Home Assistant person id", enrollment_id)
        return None
    if not isinstance(enrollment, dict):
        return None
    external = enrollment.get("external_ids")
    if not isinstance(external, dict):
        return None
    value = external.get("homeassistant")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def speaker_object(details: dict[str, Any]) -> dict[str, Any] | None:
    """Known speaker for clients that keep transcript context.

    Omitted when the gate or match did not accept a named person, so a client
    does not tell the language model that "unknown" was speaking. The transcript
    text itself is never changed here.
    """
    if not details.get("accepted"):
        return None
    name = details.get("label")
    if not isinstance(name, str) or not name.strip() or name.strip().lower() == "unknown":
        return None
    speaker: dict[str, Any] = {"name": name.strip()}
    enrollment_id = details.get("enrollment_id")
    if isinstance(enrollment_id, str) and enrollment_id.strip():
        speaker["id"] = enrollment_id.strip()
    person = details.get("person_entity_id")
    if isinstance(person, str) and person.strip():
        speaker["person_entity_id"] = person.strip()
    confidence = details.get("confidence")
    if isinstance(confidence, int | float):
        speaker["confidence"] = confidence
    return speaker


def wyoming_transcript_context(details: dict[str, Any]) -> dict[str, Any]:
    """Transcript context: full details plus a stable ``speaker`` object."""
    context: dict[str, Any] = {"openrecognition": details}
    speaker = speaker_object(details)
    if speaker is not None:
        context["speaker"] = speaker
    return context


def openrecognition_details(
    result: UtteranceResult,
    *,
    transcript: str = "",
    audio_sec: float = 0.0,
    upstream_skipped: bool = False,
    person_entity_id: str | None = None,
) -> dict[str, Any]:
    """Fields a person or automation needs for one Assist utterance."""
    scores = None
    if result.gate_scores:
        scores = {key: round(float(value), 4) for key, value in result.gate_scores.items()}
    candidates = [
        {
            "label": row.get("label"),
            "entity_id": row.get("entity_id"),
            "confidence": round(float(row.get("confidence") or 0.0), 4),
            "accepted": bool(row.get("accepted")),
        }
        for row in (result.candidates or [])
    ]
    return {
        "gate": result.gate,
        "reason": result.reason,
        "accepted": result.accepted,
        "label": result.label,
        "enrollment_id": result.enrollment_id,
        "person_entity_id": person_entity_id,
        "confidence": result.confidence,
        "min_confidence": result.min_confidence,
        "recognition_type": result.recognition_type or "speaker",
        "scores": scores,
        "candidates": candidates,
        "transcript": transcript,
        "audio_sec": round(audio_sec, 2),
        "upstream_skipped": upstream_skipped,
    }


def recognition_payload(details: dict[str, Any]) -> dict[str, Any]:
    """Webhook body in the same shape as /v1/recognize, plus the utterance fields."""
    label = details.get("label")
    accepted = bool(details.get("accepted"))
    known = accepted and label not in (None, "", "unknown")
    entities: list[dict[str, Any]] = []
    # A rejected gate must not replace the last speaker with a guess.
    # An accepted gate still reports "unknown" so Home Assistant can see that
    # somebody spoke and was not enrolled.
    if details.get("gate") == "accept" and label:
        entities.append(
            {
                "entity_id": details.get("enrollment_id"),
                "label": label,
                "type": "person",
                "recognition_type": details.get("recognition_type") or "speaker",
                "confidence": float(details.get("confidence") or 0.0),
                "modality": "audio",
                "threshold_used": details.get("min_confidence"),
                "attributes": {
                    "accepted": accepted,
                    "person_entity_id": details.get("person_entity_id"),
                },
            }
        )
    return {
        "event": "recognition.match" if known else "recognition.unknown",
        "entities": entities,
        "gate": details.get("gate"),
        "reason": details.get("reason"),
        "scores": details.get("scores"),
        "accepted": accepted,
        "transcript": details.get("transcript") or "",
        "audio_sec": details.get("audio_sec"),
        "upstream_skipped": bool(details.get("upstream_skipped")),
        "min_confidence": details.get("min_confidence"),
        "candidates": details.get("candidates") or [],
        "person_entity_id": details.get("person_entity_id"),
        "meta": {},
    }


async def announce_utterance(state: Any, details: dict[str, Any]) -> None:
    """Post the utterance to webhooks, MQTT, and presence."""
    payload = recognition_payload(details)
    try:
        await state.webhooks.dispatch_recognition(
            payload["event"],
            payload,
            debounce=False,
        )
    except Exception:
        logger.exception("Wyoming recognition webhook failed")

    for entity in payload["entities"]:
        entity_id = entity.get("entity_id")
        label = entity.get("label")
        if not entity_id or label in (None, "", "unknown"):
            continue
        extra = {
            "confidence": entity.get("confidence"),
            "modality": "audio",
            "transcript": payload.get("transcript") or "",
            "person_entity_id": payload.get("person_entity_id"),
            "gate": payload.get("gate"),
            "accepted": payload.get("accepted"),
        }
        try:
            state.mqtt.publish_recognition(label, entity.get("type") or "person", extra)
            state.gallery.update_presence(
                entity_id,
                label,
                entity.get("type") or "person",
                "audio",
                None,
                entity.get("confidence"),
            )
        except Exception:
            logger.exception("Wyoming presence update failed for %s", label)
