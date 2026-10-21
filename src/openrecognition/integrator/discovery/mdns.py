"""Browse mDNS services (Wyoming STT, Home Assistant)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

WYOMING_SERVICE_TYPE = "_wyoming._tcp.local."
HOME_ASSISTANT_SERVICE_TYPE = "_home-assistant._tcp.local."


@dataclass(frozen=True)
class DiscoveredWyoming:
    name: str
    host: str
    port: int
    uri: str


@dataclass(frozen=True)
class DiscoveredHomeAssistant:
    name: str
    host: str
    port: int
    url: str


@dataclass(frozen=True)
class MdnsBrowseResult:
    wyoming: list[DiscoveredWyoming]
    home_assistant: list[DiscoveredHomeAssistant]
    available: bool


def _friendly_name(service_type: str, qualified_name: str) -> str:
    suffix = f".{service_type}"
    if qualified_name.endswith(suffix):
        return qualified_name[: -len(suffix)]
    return qualified_name.split(".", 1)[0]


def _prop_str(properties: dict[str, Any] | None, key: str) -> str:
    if not properties:
        return ""
    val = properties.get(key)
    if val is None:
        return ""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace").strip()
    return str(val).strip()


def _primary_host(info) -> str | None:
    for addr in info.parsed_addresses():
        if ":" not in addr:
            return addr
    addrs = info.parsed_addresses()
    return addrs[0] if addrs else None


def _should_exclude_wyoming(friendly_name: str, *, exclude_name: str | None) -> bool:
    if not exclude_name:
        return False
    left = friendly_name.strip().lower().replace(" ", "-")
    right = exclude_name.strip().lower().replace(" ", "-")
    return left == right


async def browse_mdns(
    *,
    timeout: float = 3.0,
    exclude_wyoming_name: str | None = None,
) -> MdnsBrowseResult:
    """Scan the LAN for Wyoming STT and Home Assistant instances."""
    try:
        from zeroconf import ServiceStateChange
        from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf, AsyncServiceBrowser
    except ImportError:
        logger.debug("zeroconf not installed — mDNS browse unavailable")
        return MdnsBrowseResult(wyoming=[], home_assistant=[], available=False)

    pending: set[tuple[str, str]] = set()
    loop = asyncio.get_running_loop()

    def _on_service(zeroconf, service_type: str, name: str, state_change) -> None:
        if state_change is ServiceStateChange.Removed:
            return
        loop.call_soon_threadsafe(pending.add, (service_type, name))

    aiozc = AsyncZeroconf()
    browser = AsyncServiceBrowser(
        aiozc.zeroconf,
        [WYOMING_SERVICE_TYPE, HOME_ASSISTANT_SERVICE_TYPE],
        handlers=[_on_service],
    )
    try:
        await asyncio.sleep(max(timeout, 0.5))
    finally:
        await browser.async_cancel()
        await aiozc.async_close()

    wyoming: list[DiscoveredWyoming] = []
    homeassistant: list[DiscoveredHomeAssistant] = []
    resolve_zc = AsyncZeroconf()

    try:
        for service_type, name in sorted(pending):
            info = AsyncServiceInfo(service_type, name)
            try:
                await info.async_request(resolve_zc.zeroconf, 3000)
            except Exception as exc:
                logger.debug("mDNS resolve failed for %s: %s", name, exc)
                continue
            host = _primary_host(info)
            if not host or not info.port:
                continue

            if service_type == WYOMING_SERVICE_TYPE:
                friendly = _friendly_name(service_type, name)
                if _should_exclude_wyoming(friendly, exclude_name=exclude_wyoming_name):
                    continue
                wyoming.append(
                    DiscoveredWyoming(
                        name=friendly,
                        host=host,
                        port=info.port,
                        uri=f"tcp://{host}:{info.port}",
                    )
                )
            elif service_type == HOME_ASSISTANT_SERVICE_TYPE:
                props = info.properties
                location = _prop_str(props, "location_name")
                friendly = location or _friendly_name(service_type, name)
                url = (
                    _prop_str(props, "internal_url")
                    or _prop_str(props, "base_url")
                    or f"http://{host}:{info.port}"
                )
                homeassistant.append(
                    DiscoveredHomeAssistant(
                        name=friendly,
                        host=host,
                        port=info.port,
                        url=url.rstrip("/"),
                    )
                )
    finally:
        await resolve_zc.async_close()

    wyoming.sort(key=lambda s: (s.name.lower(), s.host))
    homeassistant.sort(key=lambda s: (s.name.lower(), s.host))
    return MdnsBrowseResult(
        wyoming=wyoming,
        home_assistant=homeassistant,
        available=True,
    )
