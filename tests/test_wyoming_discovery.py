"""Wyoming mDNS discovery helpers."""

import pytest

from openrecognition.integrator.wyoming.discovery import (
    advertise_host,
    tcp_endpoint,
    wyoming_ports_conflict,
)


def test_tcp_endpoint_parses_host_port():
    host, port = tcp_endpoint("tcp://0.0.0.0:10300")
    assert host == "0.0.0.0"
    assert port == 10300


def test_wyoming_ports_conflict():
    assert wyoming_ports_conflict("tcp://0.0.0.0:10300", "tcp://192.168.20.120:10300")
    assert not wyoming_ports_conflict("tcp://0.0.0.0:10301", "tcp://192.168.20.120:10300")


def test_tcp_endpoint_rejects_unix():
    with pytest.raises(ValueError, match="tcp"):
        tcp_endpoint("unix:///tmp/wyoming.sock")


def test_advertise_host_skips_wildcard_bind():
    ip = advertise_host("0.0.0.0")
    assert ip and ip != "0.0.0.0"


def test_advertise_host_uses_explicit_bind():
    assert advertise_host("192.168.1.50") == "192.168.1.50"


@pytest.mark.asyncio
async def test_discovery_register_unregister():
    pytest.importorskip("zeroconf")
    from openrecognition.integrator.wyoming.discovery import WyomingDiscovery

    discovery = WyomingDiscovery()
    ok = await discovery.register(port=45678, name="openrecognition-test")
    assert ok is True
    assert discovery.registered
    await discovery.unregister()
    assert not discovery.registered
