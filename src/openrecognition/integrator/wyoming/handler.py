"""Wyoming ASR proxy handler using in-process OpenRecognition engines."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING, Any

try:
    from wyoming.asr import Transcribe, Transcript, TranscriptStart
    from wyoming.audio import AudioChunk, AudioStart, AudioStop
    from wyoming.event import Event
    from wyoming.info import Describe, Info, SelectProgram
    from wyoming.ping import Ping, Pong
    from wyoming.server import AsyncEventHandler
except ImportError:
    AsyncEventHandler = object  # type: ignore
    Event = None  # type: ignore
    Transcribe = None  # type: ignore
    Transcript = None  # type: ignore
    TranscriptStart = None  # type: ignore
    AudioChunk = None  # type: ignore
    AudioStart = None  # type: ignore
    AudioStop = None  # type: ignore
    Describe = None  # type: ignore
    Info = None  # type: ignore
    SelectProgram = None  # type: ignore
    Ping = None  # type: ignore
    Pong = None  # type: ignore

from openrecognition.integrator.wyoming.announce import (
    announce_utterance,
    openrecognition_details,
    person_entity_id,
    wyoming_transcript_context,
)
from openrecognition.integrator.wyoming.audit import log_wyoming_utterance
from openrecognition.integrator.wyoming.info import WYOMING_ASR_PROGRAM
from openrecognition.integrator.wyoming.processor import (
    UtteranceResult,
    gate_utterance,
    identify_wav,
)
from openrecognition.integrator.wyoming.transcript_tag import tag_transcript_text
from openrecognition.integrator.wyoming.upstream import forward_pcm_to_upstream

if TYPE_CHECKING:
    from openrecognition.app_state import AppState

_LOGGER = logging.getLogger("openrecognition.wyoming")
_PROCESS_LOCK = asyncio.Lock()


class SpeakerProxyHandler(AsyncEventHandler):
    """Identify speaker via AppState, then forward PCM to upstream Wyoming STT."""

    def __init__(
        self,
        wyoming_info: Info,
        app_state: "AppState",
        upstream_uri: str,
        *,
        min_confidence: float = 0.75,
        require_speaker_match: bool = True,
        block_on_gate_reject: bool = True,
        tag_speaker: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.wyoming_info = wyoming_info
        self.app_state = app_state
        self.upstream_uri = upstream_uri
        self.min_confidence = min_confidence
        self.require_speaker_match = require_speaker_match
        self.block_on_gate_reject = block_on_gate_reject
        self.tag_speaker = tag_speaker

        self._pcm = bytearray()
        self._rate = 16000
        self._width = 2
        self._channels = 1
        self._transcribe: Any = None
        self._timestamp_ms: int | None = None
        self._t0: float | None = None
        self._pending_upstream: list[Any] = []
        self._relay_upstream = False
        self._relay_context: dict[str, Any] = {}

    def _reset_stream(self) -> None:
        self._pcm = bytearray()
        self._timestamp_ms = None
        self._t0 = time.monotonic()

    @property
    def _language(self) -> str | None:
        transcribe = self._transcribe
        if transcribe is None:
            return None
        return transcribe.language

    def _speaker_context(
        self,
        result: UtteranceResult,
        *,
        transcript: str = "",
        audio_sec: float = 0.0,
        upstream_skipped: bool = False,
    ) -> dict[str, Any]:
        details = openrecognition_details(
            result,
            transcript=transcript,
            audio_sec=audio_sec,
            upstream_skipped=upstream_skipped,
            person_entity_id=person_entity_id(self.app_state, result.enrollment_id),
        )
        return wyoming_transcript_context(details)

    def _tag_text(self, text: str, result: UtteranceResult) -> str:
        speaker = result.label if result.accepted and result.label else None
        return tag_transcript_text(text, enabled=self.tag_speaker, speaker=speaker)

    @staticmethod
    def _merge_context(
        upstream: dict[str, Any] | None,
        speaker: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(upstream or {})
        merged.update(speaker)
        return merged

    def _transcript(self, text: str, context: dict[str, Any], *, language: str | None = None):
        return Transcript(
            text=text,
            language=language if language is not None else self._language,
            context=context,
        ).event()

    async def _relay_upstream_event(self, event: Event, speaker_context: dict[str, Any]) -> None:
        """Forward streaming ASR events.

        Chunk text is relayed as the upstream service sent it. Wyoming 1.10
        chunks are fragments to append; 1.11 chunks replace the previous
        transcript. The speaker tag is applied only on the final transcript.
        """
        if TranscriptStart is not None and TranscriptStart.is_type(event.type):
            start = TranscriptStart.from_event(event)
            await self.write_event(
                TranscriptStart(
                    language=start.language or self._language,
                    context=self._merge_context(start.context, speaker_context),
                ).event()
            )
            return
        await self.write_event(event)

    async def handle_event(self, event: Event) -> bool:
        if Ping is not None and Ping.is_type(event.type):
            ping = Ping.from_event(event)
            await self.write_event(Pong(text=ping.text).event())
            return True

        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info.event())
            return True

        if SelectProgram is not None and SelectProgram.is_type(event.type):
            selected = SelectProgram.from_event(event)
            if selected.name != WYOMING_ASR_PROGRAM:
                _LOGGER.warning(
                    "Ignoring select-program %r; this service only provides %r",
                    selected.name,
                    WYOMING_ASR_PROGRAM,
                )
            return True

        if Transcribe.is_type(event.type):
            # Kept across audio-start. Resetting the buffer must not drop it.
            self._transcribe = Transcribe.from_event(event)
            return True

        if AudioStart.is_type(event.type):
            self._reset_stream()
            start = AudioStart.from_event(event)
            self._rate = start.rate
            self._width = start.width
            self._channels = start.channels
            self._timestamp_ms = start.timestamp
            return True

        if AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            self._rate = chunk.rate
            self._width = chunk.width
            self._channels = chunk.channels
            if self._timestamp_ms is None and chunk.timestamp is not None:
                self._timestamp_ms = chunk.timestamp
            self._pcm.extend(chunk.audio)
            return True

        if AudioStop.is_type(event.type):
            await self._finish_utterance()
            return True

        return True

    def _might_forward(self, gate: str) -> bool:
        """True when upstream STT might still be used after the audio gate.

        A rejected gate forces ``accepted`` false, so upstream is skipped when
        either block is on. Starting STT only in the remaining cases keeps
        noise and unknown speakers off the upstream model.
        """
        if gate == "accept":
            return True
        return not self.block_on_gate_reject and not self.require_speaker_match

    def _should_use_upstream(self, result: UtteranceResult) -> bool:
        if result.gate != "accept" and self.block_on_gate_reject:
            return False
        return result.accepted or not self.require_speaker_match

    async def _buffer_upstream_event(self, event: Event) -> None:
        """Hold streaming events until speaker ID says this utterance is used.

        Relaying early would show partial text for a speaker we then discard.
        """
        if self._relay_upstream:
            await self._relay_upstream_event(event, self._relay_context)
            return
        self._pending_upstream.append(event)

    async def _flush_upstream_events(self, context: dict[str, Any]) -> None:
        self._relay_context = context
        self._relay_upstream = True
        pending = self._pending_upstream
        self._pending_upstream = []
        for event in pending:
            await self._relay_upstream_event(event, context)

    @staticmethod
    async def _cancel_task(task: asyncio.Task | None) -> None:
        if task is None:
            return
        if not task.done():
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    async def _finish_utterance(self) -> None:
        t0 = time.perf_counter()
        pcm = bytes(self._pcm)
        self._pending_upstream = []
        self._relay_upstream = False
        self._relay_context = {}
        if not pcm:
            total_ms = (time.perf_counter() - t0) * 1000
            log_wyoming_utterance(
                self.app_state.recognition_logs,
                event="wyoming.empty",
                total_ms=total_ms,
            )
            await self.write_event(
                self._transcript("", {"openrecognition": {"gate": "empty"}})
            )
            _LOGGER.info(
                "Wyoming utterance empty (%.0f ms total)",
                total_ms,
            )
            return

        duration = len(pcm) / max(self._rate * self._width * self._channels, 1)
        _LOGGER.info("Wyoming utterance %.2fs audio — gate + identify", duration)

        loop = asyncio.get_running_loop()
        t_identify = time.perf_counter()
        async with _PROCESS_LOCK:
            gated = await loop.run_in_executor(
                None,
                lambda: gate_utterance(
                    self.app_state,
                    pcm,
                    self._rate,
                    self._width,
                    self._channels,
                ),
            )

        # Speech-to-text starts as soon as the gate allows it, and runs while
        # the speaker embedding is computed. Rejected audio never opens upstream.
        upstream_task: asyncio.Task | None = None
        t_upstream = time.perf_counter()
        if self._might_forward(gated.gate):
            upstream_task = asyncio.create_task(
                forward_pcm_to_upstream(
                    self.upstream_uri,
                    pcm,
                    self._rate,
                    self._width,
                    self._channels,
                    language=self._language,
                    transcribe=self._transcribe,
                    timestamp_ms=self._timestamp_ms,
                    on_event=self._buffer_upstream_event,
                )
            )

        try:
            async with _PROCESS_LOCK:
                result = await loop.run_in_executor(
                    None,
                    lambda: identify_wav(
                        self.app_state,
                        gated.wav,
                        gated.gate,
                        gated.reason,
                        gated.scores,
                        min_confidence=self.min_confidence,
                    ),
                )
        except BaseException:
            await self._cancel_task(upstream_task)
            raise
        identify_ms = (time.perf_counter() - t_identify) * 1000

        context = self._speaker_context(result, audio_sec=duration)
        details = context["openrecognition"]

        if not self._should_use_upstream(result):
            await self._cancel_task(upstream_task)
            total_ms = (time.perf_counter() - t0) * 1000
            if result.gate != "accept" and self.block_on_gate_reject:
                reason = result.reason or result.gate
                scores = result.gate_scores or {}
                block_reason = f"Audio gate {result.gate}: {reason}"
                _LOGGER.info(
                    "Wyoming done gate=%s reason=%s scores=%s identify=%.0fms total=%.0fms "
                    "(upstream skipped — block on gate reject is on)",
                    result.gate,
                    reason,
                    scores,
                    identify_ms,
                    total_ms,
                )
            else:
                block_reason = "Speaker not matched (require speaker match is on)"
                _LOGGER.info(
                    "Wyoming done gate=%s speaker=%s conf=%s identify=%.0fms total=%.0fms "
                    "(upstream skipped)",
                    result.gate,
                    result.label,
                    result.confidence,
                    identify_ms,
                    total_ms,
                )
            log_wyoming_utterance(
                self.app_state.recognition_logs,
                event="wyoming.blocked",
                result=result,
                audio_sec=duration,
                identify_ms=identify_ms,
                total_ms=total_ms,
                upstream_skipped=True,
                block_reason=block_reason,
            )
            details["upstream_skipped"] = True
            details["reason"] = details.get("reason") or block_reason
            await announce_utterance(self.app_state, details)
            await self.write_event(self._transcript("", context))
            return

        if result.accepted:
            _LOGGER.info(
                "Speaker %s (%.2f) — using upstream STT",
                result.label,
                result.confidence or 0.0,
            )
        elif result.gate != "accept":
            _LOGGER.info(
                "Gate %s (%s) — block on gate reject is off, using upstream STT",
                result.gate,
                result.reason or result.gate,
            )
        else:
            _LOGGER.info(
                "No speaker match (require match off) — using upstream STT",
            )

        upstream_ms = 0.0
        text = ""
        upstream_language: str | None = None
        upstream_context: dict[str, Any] | None = None
        try:
            await self._flush_upstream_events(context)
            if upstream_task is None:
                raise RuntimeError("upstream STT was not started")
            upstream = await upstream_task
            upstream_ms = (time.perf_counter() - t_upstream) * 1000
            text = upstream.text
            upstream_language = upstream.language
            upstream_context = upstream.context
        except asyncio.CancelledError:
            await self._cancel_task(upstream_task)
            raise
        except Exception:
            _LOGGER.exception("Upstream STT failed after %.0f ms identify", identify_ms)
            text = ""
            await self._cancel_task(upstream_task)

        text = self._tag_text(text, result)
        details["transcript"] = text
        details["upstream_skipped"] = False
        context = self._merge_context(upstream_context, context)
        await announce_utterance(self.app_state, details)
        total_ms = (time.perf_counter() - t0) * 1000
        log_wyoming_utterance(
            self.app_state.recognition_logs,
            event="wyoming.transcript",
            result=result,
            text=text,
            audio_sec=duration,
            identify_ms=identify_ms,
            upstream_ms=upstream_ms,
            total_ms=total_ms,
            upstream_skipped=False,
        )
        _LOGGER.info(
            "Wyoming done audio=%.2fs gate=%s speaker=%s conf=%s "
            "identify=%.0fms upstream=%.0fms total=%.0fms text=%r",
            duration,
            result.gate,
            result.label,
            result.confidence,
            identify_ms,
            upstream_ms,
            total_ms,
            text[:80] if text else "",
        )
        await self.write_event(
            self._transcript(text, context, language=upstream_language or self._language)
        )
