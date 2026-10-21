"""Runtime network context (container vs bare metal)."""

from __future__ import annotations

import os
import re
from pathlib import Path

from openrecognition.integrator.wyoming.discovery import advertise_host, tcp_endpoint

_PRIVATE_IPV4 = re.compile(
    r"^(127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|169\.254\.)"
)


def running_in_container() -> bool:
    return Path("/.dockerenv").exists() or bool(
        os.environ.get("KUBERNETES_SERVICE_HOST")
    )


def network_discovery_context(listen_uri: str, *, advertise_override: str | None) -> dict:
    """Hints for UI/docs when mDNS or LAN routing may not work."""
    try:
        _, listen_port = tcp_endpoint(listen_uri)
    except ValueError:
        listen_port = None

    detected = advertise_host(None, override=advertise_override or None)
    in_container = running_in_container()
    private_detected = bool(_PRIVATE_IPV4.match(detected))
    docker_bridge = detected.startswith("172.") and in_container

    mdns_likely_limited = in_container
    message = None
    if in_container:
        message = (
            "OpenRecognition is running in a container. mDNS (Zeroconf) usually does not "
            "reach Home Assistant on your LAN. Publish the Wyoming listen port on the host "
            "and add the Wyoming integration manually with the host IP and port."
        )
    elif docker_bridge:
        message = (
            f"Detected container-style address {detected}. Set mDNS advertise host to your "
            "LAN IP if Home Assistant cannot discover this service."
        )

    return {
        "in_container": in_container,
        "detected_host": detected,
        "listen_port": listen_port,
        "mdns_likely_limited": mdns_likely_limited,
        "manual_ha_hint": (
            f"tcp://<host-lan-ip>:{listen_port}" if listen_port else None
        ),
        "message": message,
    }
