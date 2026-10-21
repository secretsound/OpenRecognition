"""Wyoming audit log entries."""

from openrecognition.integrator.wyoming.audit import log_wyoming_utterance
from openrecognition.integrator.wyoming.processor import UtteranceResult


def test_log_wyoming_transcript(client):
    state = client.app.state.app_state
    result = UtteranceResult(
        gate="accept",
        accepted=True,
        label="Luke",
        enrollment_id="abc-123",
        confidence=0.91,
        recognition_type="speaker",
        gate_scores={"speech": 0.88, "music": 0.05, "noise": 0.07},
        candidates=[
            {
                "label": "Luke",
                "entity_id": "abc-123",
                "confidence": 0.91,
                "accepted": True,
            },
            {
                "label": "unknown",
                "entity_id": None,
                "confidence": 0.42,
                "accepted": False,
            },
        ],
        min_confidence=0.7,
    )
    log_wyoming_utterance(
        state.recognition_logs,
        event="wyoming.transcript",
        result=result,
        text="How many lights are on?",
        audio_sec=3.2,
        identify_ms=180,
        upstream_ms=6200,
        total_ms=6450,
        upstream_skipped=False,
    )

    items, total = state.recognition_logs.list_logs(limit=5)
    assert total >= 1
    row = items[0]
    assert row["event"] == "wyoming.transcript"
    assert row["label"] == "Luke"
    assert row["entity_id"] == "abc-123"
    assert row["gate"] == "accept"
    assert row["actor_type"] == "integration"
    assert row["actor_name"] == "wyoming"
    assert row["latency_ms"] == 6450
    assert "How many lights are on?" in (row["summary"] or "")
    assert "upstream 6200ms" in (row["summary"] or "")

    details = row["details"]
    assert details is not None
    assert details["gate_scores"]["speech"] == 0.88
    assert details["min_confidence"] == 0.7
    assert len(details["speaker_candidates"]) == 2
    assert details["speaker_candidates"][0]["label"] == "Luke"
    assert details["speaker_candidates"][0]["accepted"] is True
    assert details["timing_ms"]["identify"] == 180
    assert details["transcript"] == "How many lights are on?"


def test_log_wyoming_blocked(client):
    state = client.app.state.app_state
    result = UtteranceResult(
        gate="reject",
        accepted=False,
        reason="background_noise",
        gate_scores={"speech": 0.12, "music": 0.02, "noise": 0.86},
    )
    log_wyoming_utterance(
        state.recognition_logs,
        event="wyoming.blocked",
        result=result,
        audio_sec=0.4,
        identify_ms=150,
        total_ms=170,
        upstream_skipped=True,
        block_reason="Gate reject",
    )

    items, _ = state.recognition_logs.list_logs(event="wyoming.blocked", limit=1)
    assert items
    assert items[0]["gate"] == "reject"
    assert "upstream skipped" in (items[0]["summary"] or "")

    details = items[0]["details"]
    assert details is not None
    assert details["gate_scores"]["noise"] == 0.86
    assert details["block_reason"] == "Gate reject"
    assert details["upstream_skipped"] is True


def test_log_wyoming_blocked_no_entities(client):
    state = client.app.state.app_state
    result = UtteranceResult(
        gate="accept",
        accepted=False,
        reason="no_entities",
        gate_scores={"speech": 0.91, "music": 0.03, "noise": 0.06},
        candidates=[
            {
                "label": "unknown",
                "entity_id": None,
                "confidence": 0.38,
                "accepted": False,
            },
        ],
        min_confidence=0.7,
    )
    log_wyoming_utterance(
        state.recognition_logs,
        event="wyoming.blocked",
        result=result,
        audio_sec=2.57,
        identify_ms=100,
        total_ms=100,
        upstream_skipped=True,
        block_reason="Gate reject (no_entities)",
    )

    items, _ = state.recognition_logs.list_logs(event="wyoming.blocked", limit=1)
    assert items
    row = items[0]
    assert row["reason"] == "no_entities"
    assert row["confidence"] is None

    details = row["details"]
    assert details is not None
    assert details["speaker_match_attempted"] is True
    assert details["speaker_candidates"][0]["confidence"] == 0.38
    assert details["speaker_candidates"][0]["accepted"] is False
    assert details["min_confidence"] == 0.7


def test_log_wyoming_transcript_includes_speaker_attempt(client):
    state = client.app.state.app_state
    result = UtteranceResult(
        gate="accept",
        accepted=False,
        reason="no_entities",
        gate_scores={"speech": 0.74, "music": 0.23, "noise": 0.03},
        candidates=[],
        min_confidence=0.7,
        speaker_match_attempted=True,
        gallery_count=2,
        comparable_speaker_count=0,
    )
    log_wyoming_utterance(
        state.recognition_logs,
        event="wyoming.transcript",
        result=result,
        text="Hello",
        audio_sec=2.7,
        identify_ms=118,
        upstream_ms=6593,
        total_ms=6711,
    )

    items, _ = state.recognition_logs.list_logs(event="wyoming.transcript", limit=1)
    details = items[0]["details"]
    assert details["speaker_match_attempted"] is True
    assert details["speaker_candidates"] == []
    assert details["comparable_speaker_count"] == 0
