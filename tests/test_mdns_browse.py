"""mDNS browse for integrations."""

import pytest

from openrecognition.integrator.discovery.mdns import (
    HOME_ASSISTANT_SERVICE_TYPE,
    WYOMING_SERVICE_TYPE,
    _friendly_name,
    _prop_str,
    _should_exclude_wyoming,
    browse_mdns,
)


def test_friendly_name():
    assert (
        _friendly_name(WYOMING_SERVICE_TYPE, "faster-whisper._wyoming._tcp.local.")
        == "faster-whisper"
    )


def test_prop_str_bytes():
    assert _prop_str({"location_name": b"Home"}, "location_name") == "Home"


def test_exclude_self_wyoming():
    assert _should_exclude_wyoming("openrecognition", exclude_name="openrecognition")
    assert not _should_exclude_wyoming("faster-whisper", exclude_name="openrecognition")


@pytest.mark.asyncio
async def test_browse_mdns_live():
    pytest.importorskip("zeroconf")
    result = await browse_mdns(timeout=2.0, exclude_wyoming_name="openrecognition")
    assert result.available is True
    assert isinstance(result.wyoming, list)
    assert isinstance(result.home_assistant, list)


def test_discover_api(client, auth_headers):
    r = client.get("/v1/integrations/discover?timeout=1", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "available" in body
    assert "wyoming" in body
    assert "home_assistant" in body


def test_wyoming_upstream_test_api(client, auth_headers):
    r = client.post(
        "/v1/integrations/wyoming/test-upstream",
        headers=auth_headers,
        json={"uri": "tcp://127.0.0.1:1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "message" in body


def test_wyoming_home_assistant_test_api(client, auth_headers):
    r = client.post(
        "/v1/integrations/wyoming/test-home-assistant",
        headers=auth_headers,
        json={"url": ""},
    )
    assert r.status_code == 422

    r2 = client.post(
        "/v1/integrations/wyoming/test-home-assistant",
        headers=auth_headers,
        json={"url": "http://127.0.0.1:1"},
    )
    assert r2.status_code == 200
    assert r2.json()["ok"] is False
