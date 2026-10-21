"""Guards for URLs this server fetches on behalf of a caller."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

_METADATA_HOSTS = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "instance-data",
    }
)


class UnsafeUrlError(ValueError):
    """The URL must not be fetched."""


def validate_outbound_url(
    url: str,
    *,
    allow_loopback: bool = False,
    allow_unresolved: bool = False,
) -> str:
    """Allow http(s) targets and reject link-local, metadata, and (optionally) loopback hosts.

    Private LAN addresses stay allowed so homelab webhooks can reach Home Assistant.
    ``allow_unresolved`` keeps an admin-supplied hostname that DNS cannot resolve yet.
    """
    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URL credentials are not allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")
    lowered = host.lower().rstrip(".")
    if lowered in _METADATA_HOSTS:
        raise UnsafeUrlError("URL host is not allowed")
    try:
        addresses = _resolve(lowered)
    except UnsafeUrlError:
        if allow_unresolved:
            return cleaned
        raise
    for ip in addresses:
        if _blocked(ip, allow_loopback=allow_loopback):
            raise UnsafeUrlError("URL host is not allowed")
    return cleaned


def _blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_loopback: bool) -> bool:
    if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return True
    return bool(ip.is_loopback and not allow_loopback)


def _resolve(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError("URL host could not be resolved") from exc
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not addresses:
        raise UnsafeUrlError("URL host could not be resolved")
    return addresses


async def fetch_bounded(
    url: str,
    *,
    max_bytes: int,
    timeout: float = 30.0,
    allow_loopback: bool = False,
) -> bytes:
    """GET a URL without following redirects, and stop past ``max_bytes``."""
    target = validate_outbound_url(url, allow_loopback=allow_loopback, allow_unresolved=False)
    async with (
        httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client,
        client.stream("GET", target) as response,
    ):
        if response.is_redirect:
            raise UnsafeUrlError("Redirects are not followed")
        response.raise_for_status()
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise UnsafeUrlError("Response exceeds the size limit")
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise UnsafeUrlError("Response exceeds the size limit")
            chunks.append(chunk)
    return b"".join(chunks)
