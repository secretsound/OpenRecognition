"""App-agnostic speaker prefix on STT transcripts."""

from openrecognition.integrator.wyoming.transcript_tag import (
    apply_speaker_tag,
    format_speaker_tag,
    format_transcript_message,
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


def test_format_transcript_header_then_blank_line_then_stt():
    out = format_transcript_message(
        "turn on the kitchen lights",
        speaker="Luke",
        confidence=0.92,
        candidates=[
            {"label": "Luke", "confidence": 0.92},
            {"label": "Ada", "confidence": 0.41},
            {"label": "unknown", "confidence": 0.1},
        ],
        tag_speaker=True,
        include_confidence=True,
        include_candidates=True,
    )
    assert out == (
        "[speaker|confidence]\n"
        "Luke: 92%\n"
        "Ada: 41%\n"
        "\n"
        "[transcript]\n"
        "turn on the kitchen lights"
    )
    speaker, text = parse_speaker_tag(out)
    assert speaker == "Luke"
    assert text == "turn on the kitchen lights"


def test_format_transcript_candidates_only():
    out = format_transcript_message(
        "hello",
        candidates=[{"label": "Luke", "confidence": 0.8}, {"label": "Ada", "confidence": 0.5}],
        include_candidates=True,
    )
    assert out == "[speaker]\nLuke\nAda\n\n[transcript]\nhello"
    speaker, text = parse_speaker_tag(out)
    assert speaker == "Luke"
    assert text == "hello"


def test_format_transcript_includes_everyone_who_passed():
    out = format_transcript_message(
        "Can you tell who's talking right now?",
        speaker="test",
        confidence=0.56,
        candidates=[
            {"label": "test", "confidence": 0.56, "accepted": True},
            {"label": "Luke", "confidence": 0.49, "accepted": True},
            {"label": "Nova", "confidence": 0.2, "accepted": False},
        ],
        tag_speaker=True,
        include_confidence=True,
    )
    assert out == (
        "[speaker|confidence]\n"
        "test: 56%\n"
        "Luke: 49%\n"
        "\n"
        "[transcript]\n"
        "Can you tell who's talking right now?"
    )
    speaker, text = parse_speaker_tag(out)
    assert speaker == "test"
    assert text == "Can you tell who's talking right now?"


def test_format_transcript_speaker_only():
    out = format_transcript_message(
        "hello",
        speaker="Luke",
        tag_speaker=True,
    )
    assert out == "[speaker]\nLuke\n\n[transcript]\nhello"


def test_format_transcript_skips_confidence_when_nobody_matches():
    out = format_transcript_message(
        "What's the weather tomorrow?",
        speaker=None,
        confidence=0.49,
        include_confidence=True,
        tag_speaker=True,
    )
    assert out == "What's the weather tomorrow?"


def test_format_transcript_confidence_only():
    out = format_transcript_message(
        "hello",
        speaker="Luke",
        confidence=0.92,
        include_confidence=True,
    )
    assert out == "[confidence]\n92%\n\n[transcript]\nhello"


def test_format_transcript_unchanged_without_toggles():
    assert format_transcript_message("hello", speaker="Luke", confidence=0.9) == "hello"


def test_format_transcript_includes_sound_events():
    out = format_transcript_message(
        "turn on the kitchen lights",
        speaker="Luke",
        confidence=0.92,
        sound_events=[
            {"label": "bark", "confidence": 0.81},
            {"label": "glass break", "confidence": 0.44},
            {"label": "speech", "confidence": 0.9},
        ],
        tag_speaker=True,
        include_confidence=True,
        include_sound_events=True,
    )
    assert out == (
        "[speaker|confidence]\n"
        "Luke: 92%\n"
        "\n"
        "[sounds]\n"
        "bark: 81%\n"
        "glass break: 44%\n"
        "\n"
        "[transcript]\n"
        "turn on the kitchen lights"
    )
    speaker, text = parse_speaker_tag(out)
    assert speaker == "Luke"
    assert text == "turn on the kitchen lights"


def test_format_transcript_sounds_only():
    out = format_transcript_message(
        "hello",
        sound_events=[{"label": "doorbell", "confidence": 0.7}],
        include_sound_events=True,
    )
    assert out == "[sounds]\ndoorbell\n\n[transcript]\nhello"
