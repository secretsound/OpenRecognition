"""Connectivity tests for integration setup."""

from __future__ import annotations

import httpx

from openrecognition.integrator.wyoming.upstream import probe_upstream
from openrecognition.outbound import UnsafeUrlError, validate_outbound_url


def _normalize_ha_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        raise ValueError("URL is empty")
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"http://{cleaned}"
    return cleaned


async def probe_home_assistant_url(url: str, *, timeout: float = 5.0) -> dict:
    try:
        base = _normalize_ha_url(url)
        base = validate_outbound_url(base, allow_loopback=True, allow_unresolved=True)
    except (ValueError, UnsafeUrlError) as exc:
        return {"ok": False, "message": str(exc), "languages": None}

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.get(f"{base}/api/")
    except httpx.RequestError as exc:
        return {"ok": False, "message": f"Could not reach Home Assistant: {exc}", "languages": None}

    if response.status_code in (200, 401, 403):
        return {
            "ok": True,
            "message": f"Home Assistant is reachable (HTTP {response.status_code})",
            "languages": None,
        }
    return {
        "ok": False,
        "message": f"Unexpected response from Home Assistant (HTTP {response.status_code})",
        "languages": None,
    }


async def probe_upstream_uri(uri: str, *, timeout: float = 3.0) -> dict:
    cleaned = uri.strip()
    if not cleaned:
        return {"ok": False, "message": "URI is empty", "languages": None}
    if not cleaned.startswith("tcp://"):
        return {"ok": False, "message": "URI must start with tcp://", "languages": None}

    ok, message, languages = await probe_upstream(cleaned, timeout=timeout)
    return {"ok": ok, "message": message, "languages": languages or None}
