"""App-agnostic speaker prefix on STT transcripts."""

from openrecognition.integrator.wyoming.transcript_tag import (
    apply_speaker_tag,
    format_speaker_tag,
    parse_speaker_tag,
    tag_transcript_text,
)


def test_format_speaker_tag():
    assert format_speaker_tag("Luke") == "[speaker: Luke]"


def test_apply_and_parse_roundtrip():
    raw = "What's the weather today?"
    tagged = apply_speaker_tag(raw, format_speaker_tag("Luke"))
    assert tagged == "[speaker: Luke] What's the weather today?"
    speaker, text = parse_speaker_tag(tagged)
    assert speaker == "Luke"
    assert text == raw


def test_parse_case_insensitive():
    speaker, text = parse_speaker_tag("[SPEAKER: Jane] hello")
    assert speaker == "Jane"
    assert text == "hello"


def test_tag_transcript_disabled():
    assert tag_transcript_text("hello", enabled=False, speaker="Luke") == "hello"


def test_tag_transcript_skips_without_speaker():
    assert tag_transcript_text("hello", enabled=True, speaker=None) == "hello"


def test_tag_transcript_matched():
    out = tag_transcript_text("turn on the lights", enabled=True, speaker="Luke")
    speaker, text = parse_speaker_tag(out)
    assert speaker == "Luke"
    assert text == "turn on the lights"
