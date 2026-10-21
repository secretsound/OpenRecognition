"""Upstream Wyoming STT probe."""

from unittest.mock import AsyncMock, patch

import pytest

from openrecognition.integrator.wyoming.upstream import (
    query_upstream_asr,
    query_upstream_languages,
)


@pytest.mark.asyncio
async def test_query_upstream_unreachable():
    pytest.importorskip("wyoming")
    languages, ready = await query_upstream_languages(
        "tcp://127.0.0.1:1",
        timeout=0.5,
    )
    assert languages == ["en"]
    assert ready is False


@pytest.mark.asyncio
async def test_query_upstream_asr_reads_program_preferences():
    pytest.importorskip("wyoming")
    from wyoming.asr import Transcript, TranscriptChunk, TranscriptStart, TranscriptStop
    from wyoming.info import AsrModel, AsrProgram, Attribution, Info

    from openrecognition.integrator.wyoming.upstream import forward_pcm_to_upstream

    info = Info(
        asr=[
            AsrProgram(
                name="whisper",
                attribution=Attribution(name="upstream", url="https://example.test"),
                installed=True,
                description="upstream",
                version="1",
                models=[
                    AsrModel(
                        name="tiny",
                        attribution=Attribution(name="upstream", url="https://example.test"),
                        installed=True,
                        description="tiny",
                        version="1",
                        languages=["de", "en", "de"],
                    )
                ],
                supports_transcript_streaming=True,
                prefers_auto_gain_enabled=False,
                prefers_noise_reduction_enabled=False,
            )
        ]
    )
    client = AsyncMock()
    client.read_event = AsyncMock(return_value=info.event())
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    with patch(
        "openrecognition.integrator.wyoming.upstream.AsyncClient.from_uri",
        return_value=client,
    ):
        parsed = await query_upstream_asr("tcp://127.0.0.1:10300", quiet=True)

    assert parsed.reachable is True
    assert parsed.languages == ["de", "en"]
    assert parsed.supports_transcript_streaming is True
    assert parsed.prefers_auto_gain_enabled is False
    assert parsed.prefers_noise_reduction_enabled is False

    from wyoming.asr import Transcribe

    streamed: list[str] = []

    async def on_event(event) -> None:
        streamed.append(event.type)

    responses = [
        TranscriptStart(language="de").event(),
        TranscriptChunk(text="licht").event(),
        TranscriptStop().event(),
        Transcript(text="Licht an", language="de", context={"id": 1}).event(),
    ]
    forward_client = AsyncMock()
    forward_client.read_event = AsyncMock(side_effect=responses)
    forward_client.__aenter__.return_value = forward_client
    forward_client.__aexit__.return_value = None
    written: list = []

    async def write_event(event) -> None:
        written.append(event)

    forward_client.write_event = AsyncMock(side_effect=write_event)

    request = Transcribe(
        language="de",
        name="tiny",
        vad_sensitivity="relaxed",
        transcript_names=["Wohnzimmer"],
        transcript_terms=["Licht"],
    )
    with patch(
        "openrecognition.integrator.wyoming.upstream.AsyncClient.from_uri",
        return_value=forward_client,
    ) as from_uri:
        pcm = b"\x00\x00" * 16000
        result = await forward_pcm_to_upstream(
            "tcp://127.0.0.1:10300",
            pcm,
            16000,
            2,
            1,
            transcribe=request,
            timestamp_ms=15,
            on_event=on_event,
        )

    from_uri.assert_called_once_with(
        "tcp://127.0.0.1:10300",
        connect_timeout=10.0,
        read_timeout=300.0,
    )
    assert written[0].type == "transcribe"
    assert written[0].data["language"] == "de"
    assert written[0].data["name"] == "tiny"
    assert written[0].data["vad_sensitivity"] == "relaxed"
    assert written[0].data["transcript_names"] == ["Wohnzimmer"]
    assert written[0].data["transcript_terms"] == ["Licht"]
    assert written[1].type == "audio-start"
    assert written[1].data["timestamp"] == 15
    chunks = [event for event in written if event.type == "audio-chunk"]
    assert len(chunks) == 1
    assert chunks[0].payload == pcm
    assert written[-1].type == "audio-stop"
    assert written[-1].data["timestamp"] == 15 + 1000
    assert streamed == ["transcript-start", "transcript-chunk", "transcript-stop"]
    assert result.text == "Licht an"
    assert result.language == "de"
    assert result.context == {"id": 1}


def test_transcribe_for_upstream_drops_proxy_model_name():
    pytest.importorskip("wyoming")
    from wyoming.asr import Transcribe

    from openrecognition.integrator.wyoming.upstream import transcribe_for_upstream

    forwarded = transcribe_for_upstream(
        Transcribe(
            name="speaker-proxy",
            language="en",
            context={"conversation_id": "abc"},
            vad_sensitivity="aggressive",
            transcript_names=["Ada"],
            transcript_terms=["hallway"],
        )
    )
    event = forwarded.event()
    assert "name" not in event.data
    assert event.data["language"] == "en"
    assert event.data["context"] == {"conversation_id": "abc"}
    assert event.data["vad_sensitivity"] == "aggressive"
    assert event.data["transcript_names"] == ["Ada"]
    assert event.data["transcript_terms"] == ["hallway"]
