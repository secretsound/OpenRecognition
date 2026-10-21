"""Host and runtime metadata for admin settings."""

from __future__ import annotations

import platform
import socket
import sys

from openrecognition import __version__


def _lan_addresses() -> list[str]:
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0.2)
        probe.connect(("8.8.8.8", 80))
        found.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    return sorted(found)


def api_local_url(host: str, port: int) -> str:
    if host in ("0.0.0.0", "::", "[::]"):
        return f"http://127.0.0.1:{port}"
    return f"http://{host}:{port}"


def collect_system_info(
    *,
    host: str,
    port: int,
    web_origin: str | None,
) -> dict[str, object]:
    return {
        "server_version": __version__,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "lan_addresses": _lan_addresses(),
        "api_bind": f"{host}:{port}",
        "api_local_url": api_local_url(host, port),
        "web_origin": web_origin,
    }
