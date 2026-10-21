"""App-agnostic speaker prefix for STT transcripts.

Convention (any voice/assistant app may use the same pattern)::

    [speaker: Alice] turn on the kitchen lights

Parse with :func:`parse_speaker_tag` or a regex such as
``^\\[speaker:\\s*([^\\]]+)\\]\\s*``.
"""

from __future__ import annotations

import re

# [speaker: Luke] What's the weather today?
SPEAKER_TAG_RE = re.compile(
    r"^\[speaker:\s*(?P<name>[^\]]+)\]\s*",
    re.IGNORECASE,
)


def format_speaker_tag(name: str) -> str:
    """Build the speaker prefix for a matched enrollment label."""
    cleaned = " ".join(name.split())
    return f"[speaker: {cleaned}]"


def apply_speaker_tag(text: str, tag: str) -> str:
    stripped = text.strip()
    if not stripped:
        return text
    return f"{tag} {stripped}"


def parse_speaker_tag(text: str) -> tuple[str | None, str]:
    """Return ``(speaker_name, command_text)`` from a tagged transcript."""
    match = SPEAKER_TAG_RE.match(text)
    if not match:
        return None, text
    name = match.group("name").strip()
    return name, text[match.end() :].lstrip()


def tag_transcript_text(text: str, *, enabled: bool, speaker: str | None) -> str:
    """Prefix transcript when tagging is enabled and a speaker was matched."""
    if not enabled or not speaker or not text.strip():
        return text
    return apply_speaker_tag(text, format_speaker_tag(speaker))
