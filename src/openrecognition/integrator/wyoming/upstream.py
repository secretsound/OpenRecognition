"""Forward PCM to an upstream Wyoming ASR service."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from openrecognition.integrator.wyoming.info import WYOMING_ASR_MODEL

logger = logging.getLogger(__name__)

# wyoming 1.10 HTTP servers use these defaults so a stalled peer cannot hang forever.
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 300.0

try:
    from wyoming.asr import Transcribe, Transcript, TranscriptChunk, TranscriptStart, TranscriptStop
    from wyoming.audio import AudioChunk, AudioStart, AudioStop
    from wyoming.client import AsyncClient
    from wyoming.error import Error
    from wyoming.info import Describe, Info
except ImportError:
    Transcribe = None  # type: ignore
    Transcript = None  # type: ignore
    TranscriptChunk = None  # type: ignore
    TranscriptStart = None  # type: ignore
    TranscriptStop = None  # type: ignore
    AudioChunk = None  # type: ignore
    AudioStart = None  # type: ignore
    AudioStop = None  # type: ignore
    AsyncClient = None  # type: ignore
    Error = None  # type: ignore
    Describe = None  # type: ignore
    Info = None  # type: ignore


@dataclass
class UpstreamAsrInfo:
    """Describe result from the upstream Wyoming STT service."""

    languages: list[str] = field(default_factory=lambda: ["en"])
    reachable: bool = False
    supports_transcript_streaming: bool = False
    prefers_auto_gain_enabled: bool = True
    prefers_noise_reduction_enabled: bool = True


@dataclass
class UpstreamTranscript:
    """Final transcript returned by upstream STT."""

    text: str = ""
    language: str | None = None
    context: dict[str, Any] | None = None


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _asr_info_from_event(event) -> UpstreamAsrInfo | None:
    if Info is None or not Info.is_type(event.type):
        return None
    info = Info.from_event(event)
    if not info.asr:
        return UpstreamAsrInfo(reachable=True)
    # Protocol default is the first program when the client did not send select-program.
    program = info.asr[0]
    languages: list[str] = []
    for model in program.models:
        languages.extend(model.languages)
    return UpstreamAsrInfo(
        languages=_unique(languages) or ["en"],
        reachable=True,
        supports_transcript_streaming=bool(program.supports_transcript_streaming),
        prefers_auto_gain_enabled=bool(program.prefers_auto_gain_enabled),
        prefers_noise_reduction_enabled=bool(program.prefers_noise_reduction_enabled),
    )


async def query_upstream_asr(
    uri: str,
    *,
    timeout: float = 2.0,
    quiet: bool = False,
) -> UpstreamAsrInfo:
    """Probe upstream Wyoming STT for languages and ASR program preferences."""
    if AsyncClient is None:
        return UpstreamAsrInfo()
    try:
        async with AsyncClient.from_uri(
            uri,
            connect_timeout=timeout,
            read_timeout=timeout,
        ) as client:
            await client.write_event(Describe().event())
            while True:
                event = await client.read_event()
                if event is None:
                    break
                parsed = _asr_info_from_event(event)
                if parsed is not None:
                    return parsed
    except Exception as exc:
        if not quiet:
            logger.warning(
                "Upstream Wyoming STT not reachable at %s — start your STT service there "
                "(faster-whisper usually listens on port 10300). Assist transcription will fail "
                "until it is running: %s",
                uri,
                exc,
            )
        else:
            logger.debug("Upstream probe failed for %s: %s", uri, exc)
    return UpstreamAsrInfo()


async def query_upstream_languages(
    uri: str,
    *,
    timeout: float = 2.0,
    quiet: bool = False,
) -> tuple[list[str], bool]:
    """Probe upstream Wyoming STT for supported languages.

    Returns (languages, reachable). On failure uses ``["en"]`` and reachable=False.
    """
    info = await query_upstream_asr(uri, timeout=timeout, quiet=quiet)
    return info.languages, info.reachable


async def probe_upstream(uri: str, *, timeout: float = 3.0) -> tuple[bool, str, list[str]]:
    """Test upstream Wyoming STT connectivity (no log spam)."""
    if AsyncClient is None:
        return False, "Wyoming package not installed on the server", []
    info = await query_upstream_asr(uri, timeout=timeout, quiet=True)
    if info.reachable:
        lang_text = ", ".join(info.languages) if info.languages else "unknown"
        return True, f"Connected — languages: {lang_text}", info.languages
    return (
        False,
        "No response from Wyoming STT (is wyoming-faster-whisper or similar running?)",
        info.languages,
    )


def _pcm_timestamp_step(nbytes: int, rate: int, width: int, channels: int) -> int:
    frames = max(rate * width * channels, 1)
    return int(nbytes * 1000 / frames)


def _is_stream_event(event) -> bool:
    return any(
        cls is not None and cls.is_type(event.type)
        for cls in (TranscriptStart, TranscriptChunk, TranscriptStop)
    )


def transcribe_for_upstream(request: Any | None, *, language: str | None = None) -> Any:
    """Copy a client transcribe event for the upstream STT service.

    Home Assistant sends ``name`` from this proxy's info event (``speaker-proxy``).
    That name is not an upstream model, so it is omitted and the upstream service
    keeps its own default. Any other model name, plus language, context, VAD
    sensitivity, and transcript bias lists, is forwarded.
    """
    if Transcribe is None:
        raise RuntimeError("wyoming package is not installed")
    if request is None:
        return Transcribe(language=language)
    requested_language = request.language if request.language is not None else language
    name = request.name if request.name != WYOMING_ASR_MODEL else None
    return Transcribe(
        name=name,
        language=requested_language,
        context=request.context,
        vad_sensitivity=request.vad_sensitivity,
        transcript_names=request.transcript_names,
        transcript_terms=request.transcript_terms,
    )


async def forward_pcm_to_upstream(
    uri: str,
    pcm: bytes,
    rate: int,
    width: int,
    channels: int,
    *,
    language: str | None = None,
    transcribe: Any = None,
    timestamp_ms: int | None = None,
    on_event: Callable[[Any], Awaitable[None]] | None = None,
) -> UpstreamTranscript:
    """Send one utterance to upstream ASR and return the final transcript.

    Wyoming 1.10 fields (``vad_sensitivity``, ``transcript_names``,
    ``transcript_terms``, ``context``, ``language``) are forwarded. The model
    name ``speaker-proxy`` is dropped so upstream STT keeps its own model.
    Streaming events are passed to ``on_event`` unchanged so callers can relay
    them. Chunk text is not concatenated: Wyoming 1.10 chunks are fragments and
    1.11 chunks replace the previous text, and the final ``transcript`` event
    is the source of truth either way.
    """
    if AsyncClient is None or Transcribe is None:
        return UpstreamTranscript()
    request = transcribe_for_upstream(transcribe, language=language)
    timestamp = 0 if timestamp_ms is None else int(timestamp_ms)
    async with AsyncClient.from_uri(
        uri,
        connect_timeout=_CONNECT_TIMEOUT,
        read_timeout=_READ_TIMEOUT,
    ) as client:
        await client.write_event(request.event())
        await client.write_event(
            AudioStart(
                rate=rate,
                width=width,
                channels=channels,
                timestamp=timestamp,
            ).event()
        )
        # One payload so the upstream service sees audio-stop immediately and can
        # start inference while speaker identification is still running.
        if pcm:
            await client.write_event(
                AudioChunk(
                    audio=pcm,
                    rate=rate,
                    width=width,
                    channels=channels,
                    timestamp=timestamp,
                ).event()
            )
            timestamp += _pcm_timestamp_step(len(pcm), rate, width, channels)
        await client.write_event(AudioStop(timestamp=timestamp).event())
        while True:
            response = await client.read_event()
            if response is None:
                logger.error("Upstream ASR closed connection")
                return UpstreamTranscript()
            if _is_stream_event(response):
                if on_event is not None:
                    await on_event(response)
                continue
            if Error is not None and Error.is_type(response.type):
                err = Error.from_event(response)
                logger.error("Upstream ASR error: %s (%s)", err.text, err.code)
                return UpstreamTranscript()
            if Transcript.is_type(response.type):
                transcript = Transcript.from_event(response)
                return UpstreamTranscript(
                    text=transcript.text or "",
                    language=transcript.language,
                    context=transcript.context,
                )
    return UpstreamTranscript()
