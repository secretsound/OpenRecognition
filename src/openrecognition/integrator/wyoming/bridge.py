"""Optional Wyoming ASR integration (speaker proxy before upstream STT)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openrecognition.app_state import AppState

logger = logging.getLogger(__name__)

try:
    from wyoming.server import AsyncServer, AsyncTcpServer
except ImportError:
    AsyncServer = None  # type: ignore
    AsyncTcpServer = None  # type: ignore

from openrecognition.integrator.wyoming.discovery import (
    WyomingDiscovery,
    can_bind_tcp_port,
    tcp_endpoint,
    wyoming_ports_conflict,
    zeroconf_available,
)


class WyomingBridge:
    """Runs a Wyoming ASR server that uses in-process OpenRecognition for speaker ID."""

    def __init__(
        self,
        *,
        enabled: bool,
        uri: str,
        upstream_uri: str,
        min_confidence: float,
        require_speaker_match: bool,
        block_on_gate_reject: bool,
        tag_speaker: bool,
        include_confidence: bool = True,
        include_candidates: bool = False,
        include_sound_events: bool = False,
        zeroconf_enabled: bool = True,
        zeroconf_name: str = "openrecognition",
        advertise_host: str = "",
    ) -> None:
        self.enabled = enabled
        self.uri = uri
        self.upstream_uri = upstream_uri
        self.min_confidence = min_confidence
        self.require_speaker_match = require_speaker_match
        self.block_on_gate_reject = block_on_gate_reject
        self.tag_speaker = tag_speaker
        self.include_confidence = include_confidence
        self.include_candidates = include_candidates
        self.include_sound_events = include_sound_events
        self.zeroconf_enabled = zeroconf_enabled
        self.zeroconf_name = zeroconf_name
        self.advertise_host = advertise_host
        self._task: asyncio.Task | None = None
        self._app_state: AppState | None = None
        self._discovery: WyomingDiscovery | None = None
        self._upstream_languages: list[str] = ["en"]
        self._supports_transcript_streaming: bool = False
        self._prefers_auto_gain_enabled: bool = True
        self._prefers_noise_reduction_enabled: bool = True
        self.upstream_ready: bool = False
        self.zeroconf_registered: bool = False
        self.listen_error: str | None = None

    @property
    def available(self) -> bool:
        return AsyncServer is not None

    def configure(
        self,
        *,
        enabled: bool | None = None,
        uri: str | None = None,
        upstream_uri: str | None = None,
        min_confidence: float | None = None,
        require_speaker_match: bool | None = None,
        block_on_gate_reject: bool | None = None,
        tag_speaker: bool | None = None,
        include_confidence: bool | None = None,
        include_candidates: bool | None = None,
        include_sound_events: bool | None = None,
        zeroconf_enabled: bool | None = None,
        zeroconf_name: str | None = None,
        advertise_host: str | None = None,
    ) -> None:
        if enabled is not None:
            self.enabled = enabled
        if uri is not None:
            self.uri = uri
        if upstream_uri is not None:
            self.upstream_uri = upstream_uri
        if min_confidence is not None:
            self.min_confidence = min_confidence
        if require_speaker_match is not None:
            self.require_speaker_match = require_speaker_match
        if block_on_gate_reject is not None:
            self.block_on_gate_reject = block_on_gate_reject
        if tag_speaker is not None:
            self.tag_speaker = tag_speaker
        if include_confidence is not None:
            self.include_confidence = include_confidence
        if include_candidates is not None:
            self.include_candidates = include_candidates
        if include_sound_events is not None:
            self.include_sound_events = include_sound_events
        if zeroconf_enabled is not None:
            self.zeroconf_enabled = zeroconf_enabled
        if zeroconf_name is not None:
            self.zeroconf_name = zeroconf_name.strip() or "openrecognition"
        if advertise_host is not None:
            self.advertise_host = advertise_host.strip()

    async def start(self, state: "AppState") -> None:
        """Start Wyoming server if enabled."""
        self._app_state = state
        await self.restart(state)

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=2.5)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
        self.upstream_ready = False
        self._upstream_languages = ["en"]
        self._supports_transcript_streaming = False
        self._prefers_auto_gain_enabled = True
        self._prefers_noise_reduction_enabled = True
        self.zeroconf_registered = False
        self.listen_error = None
        if self._discovery is not None:
            await self._discovery.unregister()
            self._discovery = None

    async def restart(self, state: "AppState") -> None:
        from openrecognition.integrator.wyoming.upstream import query_upstream_asr

        await self.stop()
        self._app_state = state
        if not self.enabled:
            return
        if AsyncServer is None:
            logger.error(
                "Wyoming integration enabled but 'wyoming' package not installed — "
                "pip install 'openrecognition[wyoming]'"
            )
            return
        upstream = await query_upstream_asr(self.upstream_uri)
        self._upstream_languages = upstream.languages
        self.upstream_ready = upstream.reachable
        self._supports_transcript_streaming = upstream.supports_transcript_streaming
        self._prefers_auto_gain_enabled = upstream.prefers_auto_gain_enabled
        self._prefers_noise_reduction_enabled = upstream.prefers_noise_reduction_enabled
        self._task = asyncio.create_task(self._run_server(state))
        logger.info("Wyoming speaker proxy starting on %s → %s", self.uri, self.upstream_uri)

    async def _run_server(self, state: "AppState") -> None:
        from openrecognition.integrator.wyoming.handler import SpeakerProxyHandler
        from openrecognition.integrator.wyoming.info import build_wyoming_info

        discovery = WyomingDiscovery()
        self._discovery = discovery
        try:
            if wyoming_ports_conflict(self.uri, self.upstream_uri):
                self.listen_error = (
                    "Listen URI and Upstream STT URI use the same port — OpenRecognition "
                    "cannot share port 10300 with faster-whisper. Set Listen URI to another "
                    "port (e.g. tcp://0.0.0.0:10301) and point Home Assistant at that port."
                )
                logger.error(self.listen_error)
                return

            wyoming_info = build_wyoming_info(
                self._upstream_languages,
                supports_transcript_streaming=self._supports_transcript_streaming,
                prefers_auto_gain_enabled=self._prefers_auto_gain_enabled,
                prefers_noise_reduction_enabled=self._prefers_noise_reduction_enabled,
            )
            server = AsyncServer.from_uri(self.uri)

            listen_host = server.host if isinstance(server, AsyncTcpServer) else None
            listen_port = server.port if isinstance(server, AsyncTcpServer) else None
            if listen_port is None:
                try:
                    listen_host, listen_port = tcp_endpoint(self.uri)
                except ValueError:
                    listen_port = None

            if listen_port is not None:
                ok, err = can_bind_tcp_port(listen_host or "0.0.0.0", listen_port)
                if not ok:
                    self.listen_error = (
                        f"Cannot bind Wyoming listener on port {listen_port}: {err}. "
                        "Another service (often faster-whisper) may already use this port."
                    )
                    logger.error(self.listen_error)
                    return

            if self.zeroconf_enabled and listen_port is not None:
                if not zeroconf_available():
                    logger.info(
                        "Wyoming mDNS skipped (zeroconf not installed — reinstall: pip install -e .)"
                    )
                else:
                    override = self.advertise_host or None
                    if AsyncTcpServer is not None and isinstance(server, AsyncTcpServer):
                        registered = await discovery.register(
                            port=listen_port,
                            name=self.zeroconf_name,
                            host=server.host,
                            advertise_host_override=override,
                        )
                    else:
                        registered = await discovery.register(
                            port=listen_port,
                            name=self.zeroconf_name,
                            advertise_host_override=override,
                        )
                    self.zeroconf_registered = registered
                    if not registered:
                        logger.warning(
                            "Wyoming mDNS registration failed — use manual host/port in Home Assistant"
                        )

            def handler_factory(
                reader: asyncio.StreamReader,
                writer: asyncio.StreamWriter,
            ) -> SpeakerProxyHandler:
                return SpeakerProxyHandler(
                    wyoming_info,
                    state,
                    self.upstream_uri,
                    reader=reader,
                    writer=writer,
                    min_confidence=self.min_confidence,
                    require_speaker_match=self.require_speaker_match,
                    block_on_gate_reject=self.block_on_gate_reject,
                    tag_speaker=self.tag_speaker,
                    include_confidence=self.include_confidence,
                    include_candidates=self.include_candidates,
                    include_sound_events=self.include_sound_events,
                )

            await server.run(handler_factory)
        except asyncio.CancelledError:
            logger.info("Wyoming speaker proxy stopped")
            raise
        except Exception:
            logger.exception("Wyoming speaker proxy exited with error")
        finally:
            await discovery.unregister()
            if self._discovery is discovery:
                self._discovery = None
