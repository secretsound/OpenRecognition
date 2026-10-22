"""Speaker header plus STT transcript for Assist.

When extras are enabled the packet looks like::

    [speaker|confidence]
    Luke: 92%

    [sounds]
    bark: 81%
    glass break: 44%

    [transcript]
    turn on the kitchen lights

Parse with :func:`parse_speaker_tag`. The first listed name is the match.
The old one-line form ``[speaker: Luke] words`` is still accepted.
"""

from __future__ import annotations

import re
from typing import Any

# [speaker: Luke] What's the weather today?
SPEAKER_TAG_RE = re.compile(
    r"^\[speaker:\s*(?P<name>[^\]]+)\]\s*",
    re.IGNORECASE,
)
SPEAKER_SECTION_RE = re.compile(r"^\[speaker(?:\|[^\]]*)?\]\s*$", re.IGNORECASE)
TRANSCRIPT_MARK = "[transcript]"
SOUNDS_MARK = "[sounds]"
TRANSCRIPT_MARK_RE = re.compile(r"^\[transcript\]\s*", re.IGNORECASE | re.MULTILINE)


def format_speaker_tag(name: str) -> str:
    """Build the speaker prefix for a matched enrollment label."""
    cleaned = " ".join(name.split())
    return f"[speaker: {cleaned}]"


def apply_speaker_tag(text: str, tag: str) -> str:
    stripped = text.strip()
    if not stripped:
        return text
    return f"{tag} {stripped}"


def _command_text(text: str) -> str | None:
    match = TRANSCRIPT_MARK_RE.search(text)
    if match:
        return text[match.end() :].lstrip()
    if "\n\n" in text:
        return text.split("\n\n", 1)[1]
    return None


def parse_speaker_tag(text: str) -> tuple[str | None, str]:
    """Return ``(speaker_name, command_text)`` from a tagged transcript.

    Old one-line form: ``[speaker: Luke] turn on the lights``.
    Header form: ``[speaker]`` or ``[speaker|confidence]``, name rows, blank
    line, then ``[transcript]`` and the STT text.
    """
    command = _command_text(text)

    inline = SPEAKER_TAG_RE.match(text)
    if inline:
        name = inline.group("name").strip()
        if command is None:
            command = text[inline.end() :].lstrip()
        return name, command

    lines = text.splitlines()
    if lines and SPEAKER_SECTION_RE.match(lines[0]):
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped or stripped.startswith("["):
                break
            name = stripped.split(":", 1)[0].strip()
            if name:
                return name, command if command is not None else text
        return None, command if command is not None else text

    return None, text


def tag_transcript_text(text: str, *, enabled: bool, speaker: str | None) -> str:
    """Prefix transcript when tagging is enabled and a speaker was matched."""
    if not enabled or not speaker or not text.strip():
        return text
    return apply_speaker_tag(text, format_speaker_tag(speaker))


def _pct(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return f"{round(float(value) * 100)}%"


def _person_row(label: str, confidence: Any, *, include_confidence: bool) -> str:
    pct = _pct(confidence) if include_confidence else None
    return f"{label}: {pct}" if pct else label


def _named_candidates(candidates: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidates or []:
        label = str(item.get("label") or "").strip()
        if not label or label.lower() == "unknown":
            continue
        rows.append(item)
    return rows


def _passed_candidates(
    candidates: list[dict[str, Any]] | None,
    speaker: str | None,
) -> list[dict[str, Any]]:
    """People who cleared their own bar, with the chosen speaker first."""
    passed = [item for item in _named_candidates(candidates) if item.get("accepted") is True]
    primary = (speaker or "").strip().lower()

    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        label = str(item.get("label") or "").strip().lower()
        score = float(item.get("confidence") or 0.0)
        return (0 if primary and label == primary else 1, -score)

    passed.sort(key=sort_key)
    return passed


def _candidate_rows(
    candidates: list[dict[str, Any]] | None,
    *,
    include_confidence: bool,
) -> list[str]:
    return [
        _person_row(str(item.get("label")), item.get("confidence"), include_confidence=include_confidence)
        for item in _named_candidates(candidates)
    ]


def _sound_rows(
    events: list[dict[str, Any]] | None,
    *,
    include_confidence: bool,
) -> list[str]:
    rows: list[str] = []
    for item in events or []:
        label = str(item.get("label") or "").strip()
        if not label or label.lower() == "speech":
            continue
        rows.append(_person_row(label, item.get("confidence"), include_confidence=include_confidence))
    return rows


def format_transcript_message(
    text: str,
    *,
    speaker: str | None = None,
    confidence: float | None = None,
    candidates: list[dict[str, Any]] | None = None,
    sound_events: list[dict[str, Any]] | None = None,
    tag_speaker: bool = False,
    include_confidence: bool = False,
    include_candidates: bool = False,
    include_sound_events: bool = False,
) -> str:
    """Put speaker and sound blocks first, then ``[transcript]`` and the STT text."""
    rows: list[str] = []
    if include_candidates:
        rows = _candidate_rows(candidates, include_confidence=include_confidence)
    elif tag_speaker:
        # Everyone who cleared their own bar belongs in the transcript, not only the top score.
        passed = _passed_candidates(candidates, speaker)
        if passed:
            rows = [
                _person_row(str(item.get("label")), item.get("confidence"), include_confidence=include_confidence)
                for item in passed
            ]
        elif speaker:
            rows.append(_person_row(speaker, confidence, include_confidence=include_confidence))
    elif include_confidence and speaker:
        pct = _pct(confidence)
        if pct:
            rows.append(pct)

    blocks: list[list[str]] = []
    if rows:
        named = bool(include_candidates or (tag_speaker and (speaker or rows)))
        if named and include_confidence:
            title = "[speaker|confidence]"
        elif named:
            title = "[speaker]"
        else:
            title = "[confidence]"
        blocks.append([title, *rows])

    if include_sound_events:
        sounds = _sound_rows(sound_events, include_confidence=include_confidence)
        if sounds:
            blocks.append([SOUNDS_MARK, *sounds])

    if not blocks:
        return text

    header = "\n\n".join("\n".join(block) for block in blocks)
    body = text.strip()
    if not body:
        return header
    return header + "\n\n" + TRANSCRIPT_MARK + "\n" + body
