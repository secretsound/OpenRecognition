"""Home Assistant payload for a Wyoming utterance."""

from openrecognition.integrator.wyoming.announce import (
    openrecognition_details,
    person_entity_id,
    recognition_payload,
    speaker_object,
    wyoming_transcript_context,
)
from openrecognition.integrator.wyoming.processor import UtteranceResult


def test_known_speaker_payload_includes_person_and_transcript():
    result = UtteranceResult(
        gate="accept",
        accepted=True,
        label="Luke",
        enrollment_id="enr-1",
        confidence=0.91,
        recognition_type="speaker",
        min_confidence=0.75,
        gate_scores={"speech": 0.88, "music": 0.02, "noise": 0.1},
        candidates=[
            {"label": "Luke", "entity_id": "enr-1", "confidence": 0.91, "accepted": True},
            {"label": "Jane", "entity_id": "enr-2", "confidence": 0.4, "accepted": False},
        ],
    )

    class Gallery:
        def get_enrollment(self, enrollment_id):
            assert enrollment_id == "enr-1"
            return {"external_ids": {"homeassistant": "person.luke"}}

    class State:
        gallery = Gallery()

    details = openrecognition_details(
        result,
        transcript="turn on the kitchen lights",
        audio_sec=1.25,
        person_entity_id=person_entity_id(State(), "enr-1"),
    )
    payload = recognition_payload(details)

    assert payload["event"] == "recognition.match"
    assert payload["transcript"] == "turn on the kitchen lights"
    assert payload["person_entity_id"] == "person.luke"
    assert payload["gate"] == "accept"
    assert payload["scores"]["speech"] == 0.88
    assert payload["entities"][0]["label"] == "Luke"
    assert payload["entities"][0]["modality"] == "audio"
    assert payload["entities"][0]["type"] == "person"
    assert payload["entities"][0]["attributes"]["person_entity_id"] == "person.luke"
    assert payload["candidates"][1]["label"] == "Jane"
    assert details["audio_sec"] == 1.25
    context = wyoming_transcript_context(details)
    assert context["speaker"] == {
        "name": "Luke",
        "id": "enr-1",
        "person_entity_id": "person.luke",
        "confidence": 0.91,
    }
    assert context["openrecognition"]["transcript"] == "turn on the kitchen lights"


def test_gate_reject_does_not_replace_the_speaker():
    result = UtteranceResult(
        gate="reject",
        accepted=False,
        reason="background_noise",
        label=None,
    )
    payload = recognition_payload(
        openrecognition_details(result, upstream_skipped=True, audio_sec=2)
    )
    assert payload["event"] == "recognition.unknown"
    assert payload["entities"] == []
    assert payload["reason"] == "background_noise"
    assert payload["upstream_skipped"] is True
    assert "speaker" not in wyoming_transcript_context(
        openrecognition_details(result, upstream_skipped=True, audio_sec=2)
    )


def test_unknown_speaker_is_reported_without_a_person_id():
    result = UtteranceResult(
        gate="accept",
        accepted=False,
        label="unknown",
        confidence=0.42,
        reason="unknown_or_low_confidence",
    )
    payload = recognition_payload(openrecognition_details(result, transcript="hello"))
    assert payload["event"] == "recognition.unknown"
    assert payload["entities"][0]["label"] == "unknown"
    assert payload["entities"][0]["entity_id"] is None
    assert payload["transcript"] == "hello"
    assert person_entity_id(object(), None) is None
    assert speaker_object(openrecognition_details(result, transcript="hello")) is None
