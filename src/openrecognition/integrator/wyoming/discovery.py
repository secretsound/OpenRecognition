"""mDNS discovery for Home Assistant Wyoming integration."""

from __future__ import annotations

import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_MDNS_TARGET_IP = "224.0.0.251"
_WYOMING_SERVICE_TYPE = "_wyoming._tcp.local."


def zeroconf_available() -> bool:
    try:
        import zeroconf  # noqa: F401
    except ImportError:
        return False
    return True


def tcp_endpoint(uri: str) -> tuple[str, int]:
    """Parse tcp://host:port; raise if not TCP."""
    parsed = urlparse(uri)
    if parsed.scheme != "tcp" or parsed.port is None:
        raise ValueError("Zeroconf requires a tcp:// URI with an explicit port")
    host = parsed.hostname or "0.0.0.0"
    return host, int(parsed.port)


def wyoming_ports_conflict(listen_uri: str, upstream_uri: str) -> bool:
    """True when listen and upstream use the same TCP port (common misconfiguration)."""
    try:
        _, listen_port = tcp_endpoint(listen_uri)
        _, upstream_port = tcp_endpoint(upstream_uri)
    except ValueError:
        return False
    return listen_port == upstream_port


def can_bind_tcp_port(host: str, port: int) -> tuple[bool, str | None]:
    """Check whether the Wyoming listen port is free on this machine."""
    bind_host = "" if host in ("0.0.0.0", "::", "", None) else host
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((bind_host, port))
        return True, None
    except OSError as exc:
        return False, str(exc)
    finally:
        sock.close()


def advertise_host(bind_host: str | None, *, override: str | None = None) -> str:
    """Pick the LAN address HA should connect to (not 0.0.0.0)."""
    if override and override.strip():
        return override.strip()
    if bind_host and bind_host not in ("0.0.0.0", "::", ""):
        return bind_host
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        test_sock.setblocking(False)
        test_sock.connect((_MDNS_TARGET_IP, 1))
        return test_sock.getsockname()[0]
    finally:
        test_sock.close()


class WyomingDiscovery:
    """Register and unregister OpenRecognition on _wyoming._tcp.local."""

    def __init__(self) -> None:
        self._aiozc = None
        self._service_info = None

    @property
    def registered(self) -> bool:
        return self._service_info is not None

    async def register(
        self,
        *,
        port: int,
        name: str = "openrecognition",
        host: str | None = None,
        advertise_host_override: str | None = None,
    ) -> bool:
        """Advertise Wyoming STT on the local network. Returns False if zeroconf missing."""
        if not zeroconf_available():
            logger.debug("zeroconf not installed — skipping Wyoming mDNS registration")
            return False

        from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

        safe_name = name.strip().lower().replace(" ", "-") or "openrecognition"
        lan_host = advertise_host(host, override=advertise_host_override)

        self._aiozc = AsyncZeroconf()
        self._service_info = AsyncServiceInfo(
            _WYOMING_SERVICE_TYPE,
            f"{safe_name}.{_WYOMING_SERVICE_TYPE}",
            addresses=[socket.inet_aton(lan_host)],
            port=port,
        )
        await self._aiozc.async_register_service(self._service_info)
        logger.info(
            "Wyoming zeroconf: %s (%s:%s)",
            safe_name,
            lan_host,
            port,
        )
        return True

    async def unregister(self) -> None:
        if self._aiozc is None or self._service_info is None:
            return
        try:
            await self._aiozc.async_unregister_service(self._service_info)
            await self._aiozc.async_close()
        except Exception as exc:
            logger.debug("Wyoming zeroconf unregister: %s", exc)
        finally:
            self._aiozc = None
            self._service_info = None
