"""Trust forwarded headers only from configured reverse proxies."""

from __future__ import annotations

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def _settings(scope: dict):
    app = scope.get("app")
    state = getattr(getattr(app, "state", None), "app_state", None)
    if state is None:
        return None
    return state.settings


def _header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for key, value in headers:
        if key.lower() == name:
            text = value.decode("latin1").split(",")[0].strip()
            return text or None
    return None


def _replace_header(headers: list[tuple[bytes, bytes]], name: bytes, value: str) -> None:
    raw = value.encode("latin1")
    replaced = False
    kept: list[tuple[bytes, bytes]] = []
    for key, current in headers:
        if key.lower() == name:
            if not replaced:
                kept.append((name, raw))
                replaced = True
            continue
        kept.append((key, current))
    if not replaced:
        kept.append((name, raw))
    headers[:] = kept


def _safe_host(value: str) -> str | None:
    host = value.split(",")[0].strip()
    if not host or len(host) > 255:
        return None
    if any(char in host for char in " \r\n\t/@\\"):
        return None
    return host


class ForwardedProxyMiddleware:
    """Apply X-Forwarded-* when reverse proxy support is on and the peer is trusted."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        settings = _settings(scope)
        if settings is None or not settings.behind_proxy:
            await self.app(scope, receive, send)
            return
        scope = dict(scope)
        scope["headers"] = list(scope.get("headers") or [])
        proto = _header(scope["headers"], b"x-forwarded-proto")
        if proto in {"http", "https", "ws", "wss"}:
            _replace_header(scope["headers"], b"x-forwarded-proto", proto)
        host = _header(scope["headers"], b"x-forwarded-host")
        if host:
            safe = _safe_host(host)
            if safe:
                _replace_header(scope["headers"], b"host", safe)
        trusted = settings.trusted_proxies or ""
        inner = ProxyHeadersMiddleware(self.app, trusted_hosts=trusted)
        await inner(scope, receive, send)
