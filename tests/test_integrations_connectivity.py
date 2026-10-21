"""Integration connectivity probes."""

import pytest

from openrecognition.api.integrations_connectivity import probe_home_assistant_url


@pytest.mark.asyncio
async def test_home_assistant_empty_url():
    result = await probe_home_assistant_url("  ")
    assert result["ok"] is False
    assert "empty" in result["message"].lower()


@pytest.mark.asyncio
async def test_home_assistant_adds_http_scheme():
    result = await probe_home_assistant_url("127.0.0.1:1", timeout=0.5)
    assert result["ok"] is False
    assert "127.0.0.1" in result["message"] or "reach" in result["message"].lower()
