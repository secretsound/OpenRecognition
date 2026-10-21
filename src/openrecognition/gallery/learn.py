"""Save a sure voice match as a new sample for that person.

Practice runs never qualify. A learned sample uses source ``match_learn`` so it
shows up with the other samples and can be removed. User-added samples are
left in place when the learned set is trimmed.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from openrecognition.gallery.sample_meta import SampleMeta

logger = logging.getLogger(__name__)

LEARN_SOURCE = "match_learn"


def other_confidence(candidates: list[dict[str, Any]], enrollment_id: str) -> float | None:
    """Highest score belonging to someone else, if another candidate exists."""
    best: float | None = None
    for item in candidates:
        if item.get("entity_id") == enrollment_id:
            continue
        score = float(item.get("confidence") or 0.0)
        if best is None or score > best:
            best = score
    return best


def learn_allowed(
    *,
    enabled: bool,
    enrollment_type: str,
    confidence: float,
    min_confidence: float,
    margin: float,
    candidates: list[dict[str, Any]],
    enrollment_id: str,
    gate_accepted: bool,
    dry_run: bool,
    learned_today: int,
    daily_cap: int,
) -> bool:
    if dry_run or not gate_accepted or not enabled:
        return False
    if enrollment_type != "person":
        return False
    if confidence < min_confidence:
        return False
    other = other_confidence(candidates, enrollment_id)
    if other is not None and confidence - other < margin:
        return False
    if learned_today >= daily_cap:
        return False
    return True


def maybe_learn_voice(
    gallery: Any,
    enrollment_id: str | None,
    vector: np.ndarray,
    model_version: str,
    *,
    confidence: float,
    candidates: list[dict[str, Any]],
    gate_accepted: bool,
    dry_run: bool,
) -> str | None:
    """Store the embedding when this person is allowed to learn. None otherwise."""
    if not enrollment_id:
        return None
    try:
        enrollment = gallery.get_enrollment(enrollment_id)
    except Exception:
        logger.exception("Could not load enrollment %s for voice learning", enrollment_id)
        return None
    if not enrollment:
        return None
    learned_today = gallery.count_learned_today(enrollment_id)
    if not learn_allowed(
        enabled=bool(enrollment.get("learn_enabled")),
        enrollment_type=str(enrollment.get("type") or ""),
        confidence=confidence,
        min_confidence=float(enrollment.get("learn_min_confidence") or 0.9),
        margin=float(enrollment.get("learn_margin") or 0.0),
        candidates=candidates,
        enrollment_id=enrollment_id,
        gate_accepted=gate_accepted,
        dry_run=dry_run,
        learned_today=learned_today,
        daily_cap=int(enrollment.get("learn_daily_cap") or 0),
    ):
        return None
    try:
        gallery.trim_learned_samples(
            enrollment_id, int(enrollment.get("learn_max_samples") or 1)
        )
        percent = round(confidence * 100)
        sample_id = gallery.add_embedding(
            enrollment_id,
            "audio",
            vector,
            model_version,
            meta=SampleMeta(source=LEARN_SOURCE, phrase_text=f"{percent}% match"),
        )
    except Exception:
        logger.exception("Could not store a learned voice sample for %s", enrollment_id)
        return None
    logger.info(
        "Learned a voice sample for %s at %.0f%%",
        enrollment.get("label") or enrollment_id,
        confidence * 100,
    )
    return sample_id
