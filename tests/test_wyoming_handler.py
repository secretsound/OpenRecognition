"""Wyoming handler upstream forwarding rules."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from openrecognition.integrator.wyoming.processor import GatedAudio, UtteranceResult
from openrecognition.integrator.wyoming.upstream import UpstreamTranscript


@pytest.mark.asyncio
async def test_wyoming_handler_skips_upstream_on_gate_reject_when_blocking():
    from openrecognition.integrator.wyoming.handler import SpeakerProxyHandler

    rejected = UtteranceResult(
        gate="reject",
        accepted=False,
        reason="background_noise",
    )
    handler = SpeakerProxyHandler(
        wyoming_info=AsyncMock(),
        app_state=AsyncMock(),
        upstream_uri="tcp://127.0.0.1:10300",
        block_on_gate_reject=True,
        require_speaker_match=False,
        reader=AsyncMock(),
        writer=AsyncMock(),
    )
    handler._pcm = b"\x00\x01" * 8000
    handler._rate = 16000
    handler._width = 2
    handler._channels = 1
    handler.write_event = AsyncMock()
    handler.app_state.recognition_logs = AsyncMock()

    with (
        patch(
            "openrecognition.integrator.wyoming.handler.gate_utterance",
            return_value=GatedAudio(
                wav=b"wav",
                gate="reject",
                reason="background_noise",
            ),
        ),
        patch(
            "openrecognition.integrator.wyoming.handler.identify_wav",
            return_value=rejected,
        ),
        patch(
            "openrecognition.integrator.wyoming.handler.forward_pcm_to_upstream",
            new_callable=AsyncMock,
        ) as forward,
        patch(
            "openrecognition.integrator.wyoming.handler.log_wyoming_utterance",
        ) as audit,
    ):
        await handler._finish_utterance()

    forward.assert_not_called()
    audit.assert_called_once()
    assert audit.call_args.kwargs["event"] == "wyoming.blocked"
    handler.write_event.assert_called_once()


@pytest.mark.asyncio
async def test_wyoming_handler_forwards_on_gate_reject_when_not_blocking():
    from openrecognition.integrator.wyoming.handler import SpeakerProxyHandler

    rejected = UtteranceResult(
        gate="reject",
        accepted=False,
        reason="background_noise",
        gate_scores={"speech": 0.93, "music": 0.04, "noise": 0.03},
    )
    handler = SpeakerProxyHandler(
        wyoming_info=AsyncMock(),
        app_state=AsyncMock(),
        upstream_uri="tcp://127.0.0.1:10300",
        block_on_gate_reject=False,
        require_speaker_match=False,
        reader=AsyncMock(),
        writer=AsyncMock(),
    )
    handler._pcm = b"\x00\x01" * 8000
    handler._rate = 16000
    handler._width = 2
    handler._channels = 1
    handler.write_event = AsyncMock()
    handler.app_state.recognition_logs = AsyncMock()

    with (
        patch(
            "openrecognition.integrator.wyoming.handler.gate_utterance",
            return_value=GatedAudio(
                wav=b"wav",
                gate="reject",
                reason="background_noise",
            ),
        ),
        patch(
            "openrecognition.integrator.wyoming.handler.identify_wav",
            return_value=rejected,
        ),
        patch(
            "openrecognition.integrator.wyoming.handler.forward_pcm_to_upstream",
            new_callable=AsyncMock,
            return_value=UpstreamTranscript(text="turn on the lights", language="en"),
        ) as forward,
        patch(
            "openrecognition.integrator.wyoming.handler.log_wyoming_utterance",
        ) as audit,
    ):
        await handler._finish_utterance()

    forward.assert_called_once()
    audit.assert_called_once()
    assert audit.call_args.kwargs["event"] == "wyoming.transcript"
    assert audit.call_args.kwargs["text"] == "turn on the lights"
    handler.write_event.assert_called_once()
    written = handler.write_event.await_args.args[0]
    assert written.data["text"] == "turn on the lights"
    assert written.data["language"] == "en"
    spoken = written.data["context"]["openrecognition"]
    assert spoken["gate"] == "reject"
    assert spoken["reason"] == "background_noise"
    assert spoken["transcript"] == "turn on the lights"
    assert spoken["upstream_skipped"] is False
    handler.app_state.webhooks.dispatch_recognition.assert_awaited()
    dispatched = handler.app_state.webhooks.dispatch_recognition.await_args
    assert dispatched.args[0] == "recognition.unknown"
    assert dispatched.kwargs["debounce"] is False
    assert dispatched.args[1]["transcript"] == "turn on the lights"


def _handler():
    from openrecognition.integrator.wyoming.handler import SpeakerProxyHandler

    handler = SpeakerProxyHandler(
        wyoming_info=AsyncMock(),
        app_state=AsyncMock(),
        upstream_uri="tcp://127.0.0.1:10300",
        reader=AsyncMock(),
        writer=AsyncMock(),
    )
    handler.write_event = AsyncMock()
    handler.wyoming_info.event = lambda: {"type": "info"}
    return handler


@pytest.mark.asyncio
async def test_wyoming_handler_answers_ping_and_keeps_transcribe_across_audio_start():
    pytest.importorskip("wyoming")
    from wyoming.asr import Transcribe
    from wyoming.audio import AudioStart
    from wyoming.info import SelectProgram
    from wyoming.ping import Ping

    from openrecognition.integrator.wyoming.info import WYOMING_ASR_PROGRAM

    handler = _handler()
    assert await handler.handle_event(Ping(text="ready").event()) is True
    pong = handler.write_event.await_args.args[0]
    assert pong.type == "pong"
    assert pong.data["text"] == "ready"

    assert await handler.handle_event(SelectProgram(name=WYOMING_ASR_PROGRAM).event()) is True
    assert await handler.handle_event(SelectProgram(name="other-asr").event()) is True

    transcribe = Transcribe(
        name="tiny",
        language="fr",
        vad_sensitivity="aggressive",
        transcript_names=["Kitchen"],
        transcript_terms=["thermostat"],
        context={"conversation_id": "abc"},
    )
    assert await handler.handle_event(transcribe.event()) is True
    assert await handler.handle_event(
        AudioStart(rate=16000, width=2, channels=1, timestamp=40).event()
    ) is True
    assert handler._transcribe.language == "fr"
    assert handler._transcribe.transcript_names == ["Kitchen"]
    assert handler._transcribe.transcript_terms == ["thermostat"]
    assert handler._transcribe.vad_sensitivity.value == "aggressive"
    assert handler._timestamp_ms == 40


@pytest.mark.asyncio
async def test_wyoming_handler_cancels_upstream_when_speaker_is_not_matched():
    import time

    from openrecognition.integrator.wyoming.handler import SpeakerProxyHandler

    started = asyncio.Event()

    async def slow_forward(*_args, **_kwargs):
        started.set()
        await asyncio.Event().wait()
        return UpstreamTranscript(text="should not be used")

    handler = SpeakerProxyHandler(
        wyoming_info=AsyncMock(),
        app_state=AsyncMock(),
        upstream_uri="tcp://127.0.0.1:10300",
        block_on_gate_reject=False,
        require_speaker_match=True,
        reader=AsyncMock(),
        writer=AsyncMock(),
    )
    handler._pcm = b"\x00\x01" * 8000
    handler.write_event = AsyncMock()
    handler.app_state.recognition_logs = AsyncMock()
    unmatched = UtteranceResult(gate="accept", accepted=False, confidence=0.2)

    def identify_after_upstream_starts(*_args, **_kwargs):
        time.sleep(0.05)
        return unmatched

    with (
        patch(
            "openrecognition.integrator.wyoming.handler.gate_utterance",
            return_value=GatedAudio(wav=b"wav", gate="accept"),
        ),
        patch(
            "openrecognition.integrator.wyoming.handler.identify_wav",
            side_effect=identify_after_upstream_starts,
        ),
        patch(
            "openrecognition.integrator.wyoming.handler.forward_pcm_to_upstream",
            slow_forward,
        ),
        patch(
            "openrecognition.integrator.wyoming.handler.log_wyoming_utterance",
        ) as audit,
    ):
        await handler._finish_utterance()

    assert started.is_set()
    audit.assert_called_once()
    assert audit.call_args.kwargs["event"] == "wyoming.blocked"
    assert audit.call_args.kwargs["upstream_skipped"] is True
    written = handler.write_event.await_args.args[0]
    assert written.data["text"] == ""


def test_wyoming_info_advertises_protocol_preferences():
    pytest.importorskip("wyoming")
    from openrecognition.integrator.wyoming.info import WYOMING_ASR_PROGRAM, build_wyoming_info

    info = build_wyoming_info(
        ["en", "fr"],
        supports_transcript_streaming=True,
        prefers_auto_gain_enabled=False,
        prefers_noise_reduction_enabled=True,
    )
    program = info.asr[0]
    assert program.name == WYOMING_ASR_PROGRAM
    assert program.supports_transcript_streaming is True
    assert program.requires_external_vad is True
    assert program.prefers_auto_gain_enabled is False
    assert program.prefers_noise_reduction_enabled is True
    assert program.models[0].languages == ["en", "fr"]
