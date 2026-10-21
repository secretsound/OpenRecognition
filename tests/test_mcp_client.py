"""MCP HTTP client and catalog tests."""

import httpx
import pytest

from openrecognition.integrator.mcp.catalog import MCP_TOOLS, SUGGESTED_MCP_SCOPES
from openrecognition.integrator.mcp.client import OpenRecognitionApiError, OpenRecognitionClient


@pytest.mark.asyncio
async def test_client_post_file_missing(tmp_path):
    c = OpenRecognitionClient("http://test")
    with pytest.raises(FileNotFoundError):
        await c.post_file("/v1/audio/gate", str(tmp_path / "nope.wav"))


def test_client_raise_api_error():
    response = httpx.Response(403, json={"code": "FORBIDDEN", "message": "nope"})
    with pytest.raises(OpenRecognitionApiError) as exc:
        OpenRecognitionClient("http://test")._raise(response)
    assert exc.value.status == 403
    assert "nope" in exc.value.message


def test_catalog_has_expected_tools():
    names = {t["name"] for t in MCP_TOOLS}
    assert "audio_gate" in names
    assert "enroll_from_paths" in names
    assert SUGGESTED_MCP_SCOPES == ["read", "recognize", "enroll"]
