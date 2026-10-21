"""Wyoming bridge restart probes upstream before returning."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_restart_sets_upstream_ready_before_server_task():
    from openrecognition.integrator.wyoming.bridge import WyomingBridge

    bridge = WyomingBridge(
        enabled=True,
        uri="tcp://0.0.0.0:10301",
        upstream_uri="tcp://192.168.20.120:10300",
        min_confidence=0.7,
        require_speaker_match=False,
        block_on_gate_reject=False,
        tag_speaker=False,
    )
    state = AsyncMock()

    from openrecognition.integrator.wyoming.upstream import UpstreamAsrInfo

    probe = AsyncMock(
        return_value=UpstreamAsrInfo(
            languages=["en"],
            reachable=True,
            supports_transcript_streaming=True,
            prefers_auto_gain_enabled=False,
            prefers_noise_reduction_enabled=True,
        )
    )
    run_server = AsyncMock()

    async def fake_create_task(coro):
        coro.close()
        return AsyncMock()

    with (
        patch(
            "openrecognition.integrator.wyoming.upstream.query_upstream_asr",
            probe,
        ),
        patch.object(bridge, "_run_server", run_server),
        patch("openrecognition.integrator.wyoming.bridge.asyncio.create_task", fake_create_task),
        patch("openrecognition.integrator.wyoming.bridge.AsyncServer", object()),
    ):
        await bridge.restart(state)

    probe.assert_awaited_once_with("tcp://192.168.20.120:10300")
    assert bridge.upstream_ready is True
    assert bridge._upstream_languages == ["en"]
    assert bridge._supports_transcript_streaming is True
    assert bridge._prefers_auto_gain_enabled is False
